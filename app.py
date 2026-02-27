from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
import numpy as np
import pandas as pd
import io
import csv
from datetime import datetime
import json
import traceback
import math

app = Flask(__name__)
CORS(app)

class GeodeticConverter:
    """Core conversion engine for both directions"""
    
    def __init__(self, a, f):
        self.a = a
        self.f = f
        self.e2 = 2*f - f**2  # First eccentricity squared
        self.b = a * (1 - f)   # Semi-minor axis
        self.conversion_history = []  # Initialize history here
    
    def dms_to_decimal(self, dms_str):
        """
        Convert DMS string to decimal degrees
        Format: "DD° MM' SS.sss\" H" or "DD MM SS.sss H"
        """
        try:
            # Remove degree symbol and split
            dms_str = dms_str.replace('°', ' ').replace("'", ' ').replace('"', ' ').replace(',', '.')
            parts = dms_str.strip().split()
            
            if len(parts) < 4:
                raise ValueError("Invalid DMS format")
            
            degrees = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            hemisphere = parts[3].upper()
            
            decimal = degrees + minutes/60 + seconds/3600
            
            if hemisphere in ['S', 'W']:
                decimal = -decimal
            
            return decimal
        except Exception as e:
            raise ValueError(f"DMS conversion error: {str(e)}")
    
    def dms_format(self, decimal_degrees, is_latitude=True):
        """Convert decimal degrees to DMS format"""
        if decimal_degrees is None:
            return "Invalid"
        
        hemisphere = 'N' if is_latitude and decimal_degrees >= 0 else 'S' if is_latitude else 'E' if decimal_degrees >= 0 else 'W'
        
        abs_deg = abs(decimal_degrees)
        degrees = int(abs_deg)
        minutes_full = (abs_deg - degrees) * 60
        minutes = int(minutes_full)
        seconds = (minutes_full - minutes) * 60
        
        return f"{degrees}° {minutes:02d}' {seconds:06.3f}\" {hemisphere}"
    
    def get_ellipsoid_params(self):
        """Return ellipsoid parameters as a dictionary"""
        return {
            'a': self.a,
            'f': self.f,
            'e2': self.e2,
            'b': self.b
        }
    
    def cartesian_to_geodetic(self, X, Y, Z, point_name="Point", tolerance=1e-10, max_iterations=20):
        """
        Convert Cartesian coordinates to Geodetic (latitude, longitude, height)
        MINIMUM 3 ITERATIONS enforced for all points
        """
        # Store iteration details
        iterations = []
        
        # Calculate longitude (direct)
        lon = np.arctan2(Y, X)
        
        # Distance from Z-axis
        p = np.sqrt(X**2 + Y**2)
        
        # Handle special case: point on Z-axis (like North Pole)
        if p < 1e-12:
            lat = np.copysign(np.pi/2, Z)
            h = abs(Z) - self.b
            
            # Create iteration data for special case - STILL DO 3 ITERATIONS
            for i in range(3):
                iterations.append({
                    'iter': i + 1,
                    'lat': float(np.degrees(lat)),
                    'lat_rad': float(lat),
                    'h': float(h),
                    'N': float(self.a),
                    'p': float(p),
                    'sin_lat': float(np.sin(lat)),
                    'cos_lat': float(np.cos(lat)),
                    'delta_lat': 0.0,
                    'delta_lat_arcsec': 0.0,
                    'delta_h': 0.0,
                    'delta_h_mm': 0.0
                })
            
            # Normalize longitude
            lon_deg = float(np.degrees(lon))
            if lon_deg > 180:
                lon_deg -= 360
            elif lon_deg < -180:
                lon_deg += 360
            
            result = {
                'point_name': point_name,
                'input_type': 'cartesian',
                'X': float(X), 'Y': float(Y), 'Z': float(Z),
                'latitude': float(np.degrees(lat)),
                'latitude_rad': float(lat),
                'longitude': lon_deg,
                'longitude_rad': float(lon),
                'height': float(h),
                'iterations': iterations,
                'all_iterations': iterations,
                'converged': True,
                'total_iterations': 3,
                'ellipsoid_params': self.get_ellipsoid_params()
            }
            # Store in history
            self.conversion_history.append(result)
            return result
        
        # Initial latitude estimate for non-special cases
        lat = np.arctan2(Z, p * (1 - self.e2))
        
        # Iterate - ensure at least 3 iterations
        converged = False
        for i in range(max_iterations):
            lat_prev = lat
            
            # Calculate radius of curvature
            sin_lat = np.sin(lat)
            cos_lat = np.cos(lat)
            N = self.a / np.sqrt(1 - self.e2 * sin_lat**2)
            
            # Calculate height
            if abs(cos_lat) > 1e-12:
                h = p / cos_lat - N
            else:
                h = Z / sin_lat - N * (1 - self.e2)
            
            # Update latitude
            denominator = p * (1 - self.e2 * N / (N + h))
            if abs(denominator) > 1e-12:
                lat = np.arctan2(Z, denominator)
            else:
                lat = np.copysign(np.pi/2, Z)
            
            # Calculate changes
            delta_lat = abs(lat - lat_prev)
            delta_lat_arcsec = float(np.degrees(delta_lat) * 3600)
            
            if i > 0:
                # Calculate delta_h using previous height
                prev_h = iterations[-1]['h']
                delta_h = abs(h - prev_h)
                delta_h_mm = float(delta_h * 1000)
            else:
                delta_h = float('inf')
                delta_h_mm = float('inf')
            
            # Store iteration data with all parameters
            iterations.append({
                'iter': i + 1,
                'lat': float(np.degrees(lat)),
                'lat_rad': float(lat),
                'h': float(h),
                'N': float(N),
                'p': float(p),
                'sin_lat': float(sin_lat),
                'cos_lat': float(cos_lat),
                'delta_lat': float(delta_lat) if i > 0 else 0,
                'delta_lat_arcsec': delta_lat_arcsec if i > 0 else 0,
                'delta_h': float(delta_h) if i > 0 else 0,
                'delta_h_mm': delta_h_mm if i > 0 else 0
            })
            
            # Check convergence - but continue if less than 3 iterations
            if i >= 2:  # After 3 iterations (0,1,2)
                if delta_lat < tolerance and delta_h < tolerance * self.a:
                    converged = True
                    break
        
        # Ensure we have at least 3 iterations
        while len(iterations) < 3:
            iterations.append({
                'iter': len(iterations) + 1,
                'lat': iterations[-1]['lat'] if iterations else 0,
                'lat_rad': iterations[-1]['lat_rad'] if iterations else 0,
                'h': iterations[-1]['h'] if iterations else 0,
                'N': iterations[-1]['N'] if iterations else self.a,
                'p': p,
                'sin_lat': np.sin(np.radians(iterations[-1]['lat'])) if iterations else 0,
                'cos_lat': np.cos(np.radians(iterations[-1]['lat'])) if iterations else 1,
                'delta_lat': 0.0,
                'delta_lat_arcsec': 0.0,
                'delta_h': 0.0,
                'delta_h_mm': 0.0
            })
        
        # Normalize longitude
        lon_deg = float(np.degrees(lon))
        if lon_deg > 180:
            lon_deg -= 360
        elif lon_deg < -180:
            lon_deg += 360
        
        result = {
            'point_name': point_name,
            'input_type': 'cartesian',
            'X': float(X), 'Y': float(Y), 'Z': float(Z),
            'latitude': float(np.degrees(lat)),
            'latitude_rad': float(lat),
            'longitude': lon_deg,
            'longitude_rad': float(lon),
            'height': float(h),
            'iterations': iterations[:3],  # Only show first 3 iterations in UI
            'all_iterations': iterations,   # Store all for report
            'converged': converged,
            'total_iterations': len(iterations),
            'ellipsoid_params': self.get_ellipsoid_params()
        }
        
        # Store in history
        self.conversion_history.append(result)
        return result
    
    def geodetic_to_cartesian(self, lat_deg, lon_deg, h, point_name="Point"):
        """
        Convert Geodetic coordinates (latitude, longitude, height) to Cartesian (X, Y, Z)
        Direct conversion - no iteration needed
        """
        # Convert to radians
        lat = np.radians(lat_deg)
        lon = np.radians(lon_deg)
        
        # Calculate radius of curvature in prime vertical
        sin_lat = np.sin(lat)
        cos_lat = np.cos(lat)
        N = self.a / np.sqrt(1 - self.e2 * sin_lat**2)
        
        # Calculate Cartesian coordinates
        X = (N + h) * cos_lat * np.cos(lon)
        Y = (N + h) * cos_lat * np.sin(lon)
        Z = (N * (1 - self.e2) + h) * sin_lat
        
        # Create result (no iterations needed for this direction)
        result = {
            'point_name': point_name,
            'input_type': 'geodetic',
            'latitude': float(lat_deg),
            'latitude_rad': float(lat),
            'longitude': float(lon_deg),
            'longitude_rad': float(lon),
            'height': float(h),
            'X': float(X),
            'Y': float(Y),
            'Z': float(Z),
            'N': float(N),
            'sin_lat': float(sin_lat),
            'cos_lat': float(cos_lat),
            'converged': True,
            'total_iterations': 1,  # Direct calculation
            'ellipsoid_params': self.get_ellipsoid_params()
        }
        
        # Store in history
        self.conversion_history.append(result)
        return result
    
    def convert_point(self, X, Y, Z, point_name="Point", tolerance=1e-10, max_iterations=20):
        """Wrapper for backward compatibility"""
        return self.cartesian_to_geodetic(X, Y, Z, point_name, tolerance, max_iterations)

# Store converter instances in memory
converters = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/init', methods=['POST'])
def init_converter():
    try:
        data = request.json
        a = float(data['a'])
        f = float(data['f'])
        
        # Create a unique session ID
        session_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
        converters[session_id] = GeodeticConverter(a, f)
        
        converter = converters[session_id]
        
        print(f"✅ Converter initialized with session ID: {session_id}")
        print(f"   a={a}, f={f}, e2={converter.e2}, b={converter.b}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'a': a,
            'f': f,
            'e2': converter.e2,
            'b': converter.b,
            'message': 'Converter initialized successfully'
        })
    except Exception as e:
        print(f"❌ Error in init_converter: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/convert/cartesian-to-geodetic', methods=['POST'])
def convert_cartesian_to_geodetic():
    try:
        data = request.json
        session_id = data.get('session_id')
        
        print(f"🔍 Cartesian→Geodetic request for session: {session_id}")
        
        if not session_id or session_id not in converters:
            return jsonify({'success': False, 'error': 'Please initialize converter first'}), 400
        
        converter = converters[session_id]
        
        X = float(data['X'])
        Y = float(data['Y'])
        Z = float(data['Z'])
        point_name = data.get('point_name', 'Point')
        
        result = converter.cartesian_to_geodetic(X, Y, Z, point_name)
        
        # Add DMS format
        result['latitude_dms'] = converter.dms_format(result['latitude'], True)
        result['longitude_dms'] = converter.dms_format(result['longitude'], False)
        
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/convert/geodetic-to-cartesian', methods=['POST'])
def convert_geodetic_to_cartesian():
    try:
        data = request.json
        session_id = data.get('session_id')
        
        print(f"🔍 Geodetic→Cartesian request for session: {session_id}")
        
        if not session_id or session_id not in converters:
            return jsonify({'success': False, 'error': 'Please initialize converter first'}), 400
        
        converter = converters[session_id]
        
        lat = float(data['latitude'])
        lon = float(data['longitude'])
        h = float(data['height'])
        point_name = data.get('point_name', 'Point')
        
        # Handle DMS input if provided
        if data.get('latitude_dms'):
            lat = converter.dms_to_decimal(data['latitude_dms'])
        if data.get('longitude_dms'):
            lon = converter.dms_to_decimal(data['longitude_dms'])
        
        result = converter.geodetic_to_cartesian(lat, lon, h, point_name)
        
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/convert/batch', methods=['POST'])
def convert_batch():
    try:
        session_id = request.form.get('session_id')
        conversion_type = request.form.get('conversion_type', 'cartesian-to-geodetic')
        
        print(f"🔍 Batch request for session: {session_id}, type: {conversion_type}")
        
        if not session_id or session_id not in converters:
            return jsonify({'success': False, 'error': 'Please initialize converter first'}), 400
        
        converter = converters[session_id]
        
        # Get file from request
        file = request.files.get('file')
        if not file:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        # Read CSV
        content = file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        
        results = []
        errors = []
        
        for i, row in enumerate(reader, 1):
            try:
                name = row.get('Point_Name', row.get('Point', row.get('Name', f"Point_{i}")))
                
                if conversion_type == 'cartesian-to-geodetic':
                    X = float(row.get('X', row.get('X (m)', 0)))
                    Y = float(row.get('Y', row.get('Y (m)', 0)))
                    Z = float(row.get('Z', row.get('Z (m)', 0)))
                    result = converter.cartesian_to_geodetic(X, Y, Z, name)
                    result['latitude_dms'] = converter.dms_format(result['latitude'], True)
                    result['longitude_dms'] = converter.dms_format(result['longitude'], False)
                else:  # geodetic-to-cartesian
                    lat = float(row.get('Latitude', row.get('lat', 0)))
                    lon = float(row.get('Longitude', row.get('lon', 0)))
                    h = float(row.get('Height', row.get('h', row.get('height', 0))))
                    result = converter.geodetic_to_cartesian(lat, lon, h, name)
                
                results.append(result)
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")
        
        return jsonify({
            'success': True,
            'results': results,
            'errors': errors,
            'total_processed': len(results),
            'total_errors': len(errors)
        })
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/report', methods=['POST'])
def generate_report():
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id or session_id not in converters:
            return jsonify({'success': False, 'error': 'No conversion history found'}), 400
        
        converter = converters[session_id]
        
        if not hasattr(converter, 'conversion_history') or len(converter.conversion_history) == 0:
            return jsonify({'success': False, 'error': 'No conversions performed yet'}), 400
        
        # Add DMS format to any missing entries
        for entry in converter.conversion_history:
            if entry.get('input_type') == 'cartesian' and 'latitude_dms' not in entry:
                entry['latitude_dms'] = converter.dms_format(entry['latitude'], True)
                entry['longitude_dms'] = converter.dms_format(entry['longitude'], False)
        
        return jsonify({
            'success': True,
            'history': converter.conversion_history,
            'ellipsoid_params': converter.get_ellipsoid_params()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/clear', methods=['POST'])
def clear_history():
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if session_id in converters and hasattr(converters[session_id], 'conversion_history'):
            converters[session_id].conversion_history = []
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/export/csv', methods=['POST'])
def export_csv():
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id or session_id not in converters:
            return jsonify({'success': False, 'error': 'No results to export'}), 400
        
        converter = converters[session_id]
        
        if not hasattr(converter, 'conversion_history') or not converter.conversion_history:
            return jsonify({'success': False, 'error': 'No conversions to export'}), 400
        
        # Create DataFrame
        data_rows = []
        for r in converter.conversion_history:
            e_params = r.get('ellipsoid_params', converter.get_ellipsoid_params())
            
            if r.get('input_type') == 'cartesian':
                # Cartesian to Geodetic entry
                iter_summary = "; ".join([f"Iter{it['iter']}:{it['lat']:.6f}°/{it['h']:.1f}m" 
                                         for it in r.get('all_iterations', r.get('iterations', []))[:3]])
                
                data_rows.append({
                    'Conversion_Type': 'Cartesian→Geodetic',
                    'Point_Name': r['point_name'],
                    'X_m': r['X'],
                    'Y_m': r['Y'],
                    'Z_m': r['Z'],
                    'Latitude_deg': r['latitude'],
                    'Longitude_deg': r['longitude'],
                    'Height_m': r['height'],
                    'Latitude_DMS': converter.dms_format(r['latitude'], True),
                    'Longitude_DMS': converter.dms_format(r['longitude'], False),
                    'Iterations': r['total_iterations'],
                    'Iteration_Details': iter_summary
                })
            else:
                # Geodetic to Cartesian entry
                data_rows.append({
                    'Conversion_Type': 'Geodetic→Cartesian',
                    'Point_Name': r['point_name'],
                    'Latitude_deg': r['latitude'],
                    'Longitude_deg': r['longitude'],
                    'Height_m': r['height'],
                    'Latitude_DMS': converter.dms_format(r['latitude'], True),
                    'Longitude_DMS': converter.dms_format(r['longitude'], False),
                    'X_m': r['X'],
                    'Y_m': r['Y'],
                    'Z_m': r['Z'],
                    'N_m': r.get('N', 0),
                    'Iterations': r['total_iterations']
                })
        
        df = pd.DataFrame(data_rows)
        
        # Create CSV in memory with UTF-8 BOM for Excel
        output = io.StringIO()
        df.to_csv(output, index=False, encoding='utf-8')
        output.seek(0)
        
        mem = io.BytesIO()
        mem.write('\ufeff'.encode('utf-8'))
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        
        filename = f'conversion_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return send_file(
            mem,
            mimetype='text/csv; charset=utf-8',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

if __name__ == '__main__':
    print("🚀 Starting Geodetic Converter Server...")
    print("📡 Server will run at: http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)