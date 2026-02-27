from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
import numpy as np
import pandas as pd
import io
import csv
from datetime import datetime
import json
import traceback

app = Flask(__name__)
CORS(app)

class GeodeticConverter:
    """Core conversion engine"""
    
    def __init__(self, a, f):
        self.a = a
        self.f = f
        self.e2 = 2*f - f**2  # First eccentricity squared
        self.b = a * (1 - f)   # Semi-minor axis
        self.conversion_history = []  # Initialize history here
    
    def dms_format(self, decimal_degrees, is_latitude=True):
        """Convert to Degrees Minutes Seconds format"""
        if decimal_degrees is None:
            return "Invalid"
        
        hemisphere = 'N' if is_latitude and decimal_degrees >= 0 else 'S' if is_latitude else 'E' if decimal_degrees >= 0 else 'W'
        
        degrees = int(abs(decimal_degrees))
        minutes_full = (abs(decimal_degrees) - degrees) * 60
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
    
    def convert_point(self, X, Y, Z, point_name="Point", tolerance=1e-10, max_iterations=20):
        """
        Convert a single point with iteration tracking
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

@app.route('/api/convert/single', methods=['POST'])
def convert_single():
    try:
        data = request.json
        session_id = data.get('session_id')
        
        print(f"🔍 Single conversion request for session: {session_id}")
        
        if not session_id or session_id not in converters:
            return jsonify({'success': False, 'error': 'Please initialize converter first (invalid or missing session)'}), 400
        
        converter = converters[session_id]
        
        X = float(data['X'])
        Y = float(data['Y'])
        Z = float(data['Z'])
        point_name = data.get('point_name', 'Point')
        
        print(f"   Converting: {point_name} ({X}, {Y}, {Z})")
        
        result = converter.convert_point(X, Y, Z, point_name)
        
        # Add DMS format
        result['latitude_dms'] = converter.dms_format(result['latitude'], True)
        result['longitude_dms'] = converter.dms_format(result['longitude'], False)
        
        print(f"   ✅ Conversion complete. History length: {len(converter.conversion_history)}")
        
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        print(f"❌ Error in convert_single: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/convert/batch', methods=['POST'])
def convert_batch():
    try:
        session_id = request.form.get('session_id')
        
        print(f"🔍 Batch conversion request for session: {session_id}")
        
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
                X = float(row.get('X', row.get('X (m)', 0)))
                Y = float(row.get('Y', row.get('Y (m)', 0)))
                Z = float(row.get('Z', row.get('Z (m)', 0)))
                
                result = converter.convert_point(X, Y, Z, name)
                
                # Add DMS format
                result['latitude_dms'] = converter.dms_format(result['latitude'], True)
                result['longitude_dms'] = converter.dms_format(result['longitude'], False)
                
                results.append(result)
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")
        
        print(f"   ✅ Batch complete. Processed: {len(results)}, Errors: {len(errors)}")
        print(f"   History length now: {len(converter.conversion_history)}")
        
        return jsonify({
            'success': True,
            'results': results,
            'errors': errors,
            'total_processed': len(results),
            'total_errors': len(errors)
        })
    except Exception as e:
        print(f"❌ Error in convert_batch: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/report', methods=['POST'])
def generate_report():
    try:
        data = request.json
        session_id = data.get('session_id')
        
        print(f"🔍 Report request for session: {session_id}")
        
        if not session_id or session_id not in converters:
            return jsonify({'success': False, 'error': 'No conversion history found - invalid session'}), 400
        
        converter = converters[session_id]
        
        # Check if history exists and has entries
        if not hasattr(converter, 'conversion_history'):
            converter.conversion_history = []
        
        if len(converter.conversion_history) == 0:
            return jsonify({'success': False, 'error': 'No conversions performed yet'}), 400
        
        print(f"   ✅ Report generated with {len(converter.conversion_history)} entries")
        
        # Add ellipsoid parameters to each history entry if not already there
        for entry in converter.conversion_history:
            if 'ellipsoid_params' not in entry:
                entry['ellipsoid_params'] = converter.get_ellipsoid_params()
        
        return jsonify({
            'success': True,
            'history': converter.conversion_history,
            'ellipsoid_params': converter.get_ellipsoid_params()
        })
    except Exception as e:
        print(f"❌ Error in generate_report: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/clear', methods=['POST'])
def clear_history():
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if session_id in converters and hasattr(converters[session_id], 'conversion_history'):
            converters[session_id].conversion_history = []
            print(f"✅ Cleared history for session {session_id}")
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Error in clear_history: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/export/csv', methods=['POST'])
def export_csv():
    try:
        data = request.json
        session_id = data.get('session_id')
        
        print(f"🔍 Export CSV request for session: {session_id}")
        
        if not session_id or session_id not in converters:
            return jsonify({'success': False, 'error': 'No results to export - invalid session'}), 400
        
        converter = converters[session_id]
        
        if not hasattr(converter, 'conversion_history') or not converter.conversion_history:
            return jsonify({'success': False, 'error': 'No conversions to export'}), 400
        
        # Create DataFrame with all parameters and iterations
        data_rows = []
        for r in converter.conversion_history:
            # Get ellipsoid parameters
            e_params = r.get('ellipsoid_params', converter.get_ellipsoid_params())
            
            # Create detailed iteration summary with proper degree symbol
            iter_details = []
            for it in r.get('all_iterations', r['iterations']):
                iter_details.append(
                    f"Iter{it['iter']}: lat={it['lat']:.8f}° h={it['h']:.3f}m "
                    f"Δlat={it['delta_lat_arcsec']:.6f}\" Δh={it['delta_h_mm']:.3f}mm"
                )
            
            iter_summary = " | ".join(iter_details)
            
            # Get DMS with proper degree symbol
            lat_dms = converter.dms_format(r['latitude'], True)
            lon_dms = converter.dms_format(r['longitude'], False)
            
            # Add main row with all parameters
            data_rows.append({
                'Point_Name': r['point_name'],
                'X_m': r['X'],
                'Y_m': r['Y'],
                'Z_m': r['Z'],
                'Latitude_deg': r['latitude'],
                'Longitude_deg': r['longitude'],
                'Height_m': r['height'],
                'Latitude_DMS': lat_dms,
                'Longitude_DMS': lon_dms,
                'Total_Iterations': r['total_iterations'],
                'Converged': r['converged'],
                'Ellipsoid_a_m': e_params['a'],
                'Ellipsoid_f': e_params['f'],
                'Ellipsoid_e2': e_params['e2'],
                'Ellipsoid_b_m': e_params['b'],
                'Iteration_Details': iter_summary
            })
            
            # Add individual iteration rows for detailed analysis
            for it in r.get('all_iterations', r['iterations']):
                # Create DMS for this iteration's latitude
                iter_lat_dms = converter.dms_format(it['lat'], True)
                
                data_rows.append({
                    'Point_Name': f"{r['point_name']}_Iter{it['iter']}",
                    'X_m': r['X'],
                    'Y_m': r['Y'],
                    'Z_m': r['Z'],
                    'Latitude_deg': it['lat'],
                    'Longitude_deg': r['longitude'],
                    'Height_m': it['h'],
                    'Latitude_DMS': iter_lat_dms,
                    'Longitude_DMS': lon_dms,
                    'Total_Iterations': r['total_iterations'],
                    'Converged': r['converged'],
                    'Ellipsoid_a_m': e_params['a'],
                    'Ellipsoid_f': e_params['f'],
                    'Ellipsoid_e2': e_params['e2'],
                    'Ellipsoid_b_m': e_params['b'],
                    'Iteration_Number': it['iter'],
                    'N_m': it.get('N', 0),
                    'p_m': it.get('p', 0),
                    'sin_lat': it.get('sin_lat', 0),
                    'cos_lat': it.get('cos_lat', 0),
                    'Delta_Lat_rad': it.get('delta_lat', 0),
                    'Delta_Lat_arcsec': it.get('delta_lat_arcsec', 0),
                    'Delta_H_m': it.get('delta_h', 0),
                    'Delta_H_mm': it.get('delta_h_mm', 0)
                })
        
        df = pd.DataFrame(data_rows)
        
        # Create CSV in memory with UTF-8 encoding to preserve degree symbol
        output = io.StringIO()
        df.to_csv(output, index=False, encoding='utf-8')
        output.seek(0)
        
        # Create bytes object for sending with UTF-8 BOM for Excel compatibility
        mem = io.BytesIO()
        # Add UTF-8 BOM for Excel to recognize UTF-8
        mem.write('\ufeff'.encode('utf-8'))
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        
        filename = f'conversion_results_detailed_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        print(f"   ✅ CSV exported: {filename} with {len(data_rows)} rows")
        
        return send_file(
            mem,
            mimetype='text/csv; charset=utf-8',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print(f"❌ Error in export_csv: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400 
    
    
if __name__ == '__main__':
    app.run(debug=True)