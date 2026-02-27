// Global variables
let sessionId = null;
let conversionHistory = [];

// DOM Elements
document.addEventListener('DOMContentLoaded', function() {
    console.log("🚀 Application loaded");
    
    // Initialize event listeners
    setupEventListeners();
    
    // Link f and 1/f
    document.getElementById('f_value').addEventListener('input', updateFInv);
    document.getElementById('f_inv_value').addEventListener('input', updateFFromInv);
    
    // Toggle input methods
    document.getElementById('uploadRadio').addEventListener('change', toggleInputMethod);
    document.getElementById('pasteRadio').addEventListener('change', toggleInputMethod);
});

function setupEventListeners() {
    // Initialize converter
    document.getElementById('initBtn').addEventListener('click', initConverter);
    
    // Single point conversion
    document.getElementById('convertSingleBtn').addEventListener('click', convertSingle);
    document.getElementById('examplePoints').addEventListener('change', loadExample);
    
    // Batch processing
    document.getElementById('showSampleBtn').addEventListener('click', showSample);
    document.getElementById('processBatchBtn').addEventListener('click', processBatch);
    
    // Reports
    document.getElementById('generateReportBtn').addEventListener('click', generateReport);
    document.getElementById('printReportBtn').addEventListener('click', printReport);
    document.getElementById('saveCsvBtn').addEventListener('click', saveToCSV);
    document.getElementById('clearBtn').addEventListener('click', clearResults);
}

function updateFInv() {
    const f = parseFloat(document.getElementById('f_value').value);
    if (f && f > 0) {
        document.getElementById('f_inv_value').value = 1 / f;
    }
}

function updateFFromInv() {
    const fInv = parseFloat(document.getElementById('f_inv_value').value);
    if (fInv && fInv > 0) {
        document.getElementById('f_value').value = 1 / fInv;
    }
}

function toggleInputMethod() {
    const uploadContainer = document.getElementById('uploadContainer');
    const manualContainer = document.getElementById('manualContainer');
    
    if (document.getElementById('uploadRadio').checked) {
        uploadContainer.style.display = 'block';
        manualContainer.style.display = 'none';
    } else {
        uploadContainer.style.display = 'none';
        manualContainer.style.display = 'block';
    }
}

async function initConverter() {
    const a = parseFloat(document.getElementById('a_value').value);
    const f = parseFloat(document.getElementById('f_value').value);
    
    if (!a || !f) {
        showError('initOutput', 'Please enter valid values');
        return;
    }
    
    try {
        console.log("Initializing converter with a=" + a + ", f=" + f);
        
        const response = await fetch('/api/init', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({a, f})
        });
        
        const data = await response.json();
        console.log("Init response:", data);
        
        if (data.success) {
            sessionId = data.session_id;
            console.log("✅ Session ID set to:", sessionId);
            
            // Clear previous history
            conversionHistory = [];
            
            showSuccess('initOutput', `
                <strong>✅ Converter initialized successfully!</strong><br>
                <strong>Session ID:</strong> ${sessionId}<br>
                <strong>Ellipsoid Parameters:</strong><br>
                a = ${data.a.toLocaleString()} m<br>
                f = ${data.f}<br>
                1/f = ${(1/data.f).toFixed(6)}<br>
                e² = ${data.e2.toFixed(10)}<br>
                b = ${data.b.toLocaleString()} m<br>
                <span class="badge bg-info">MINIMUM 3 ITERATIONS will be performed for all points</span>
            `);
        } else {
            showError('initOutput', data.error);
        }
    } catch (error) {
        console.error("Init error:", error);
        showError('initOutput', error.message);
    }
}

function loadExample() {
    const select = document.getElementById('examplePoints');
    if (select.value) {
        const [x, y, z] = select.value.split(',').map(Number);
        document.getElementById('xValue').value = x;
        document.getElementById('yValue').value = y;
        document.getElementById('zValue').value = z;
    }
}

async function convertSingle() {
    if (!sessionId) {
        showError('singleOutput', 'Please initialize converter first! Click "Initialize Converter" in Step 1.');
        return;
    }
    
    const pointName = document.getElementById('pointName').value || 'Point';
    const X = parseFloat(document.getElementById('xValue').value) || 0;
    const Y = parseFloat(document.getElementById('yValue').value) || 0;
    const Z = parseFloat(document.getElementById('zValue').value) || 0;
    
    console.log("Converting single point with session:", sessionId, pointName, X, Y, Z);
    
    try {
        const response = await fetch('/api/convert/single', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                session_id: sessionId,
                point_name: pointName, 
                X: X, 
                Y: Y, 
                Z: Z
            })
        });
        
        const data = await response.json();
        console.log("Single conversion response:", data);
        
        if (data.success) {
            // Add to local history
            conversionHistory.push(data.result);
            displaySingleResult(data.result);
        } else {
            showError('singleOutput', data.error || 'Conversion failed');
        }
    } catch (error) {
        console.error("Single conversion error:", error);
        showError('singleOutput', error.message);
    }
}

function displaySingleResult(result) {
    const output = document.getElementById('singleOutput');
    
    let html = `
        <div class="alert alert-success">
            <h6 class="alert-heading">✅ Conversion complete for ${result.point_name}</h6>
            <hr>
            <div class="row">
                <div class="col-md-6">
                    <strong>📌 INPUT:</strong><br>
                    X = ${result.X.toLocaleString()} m<br>
                    Y = ${result.Y.toLocaleString()} m<br>
                    Z = ${result.Z.toLocaleString()} m
                </div>
                <div class="col-md-6">
                    <strong>📍 OUTPUT:</strong><br>
                    Latitude: ${result.latitude.toFixed(10)}°<br>
                    Longitude: ${result.longitude.toFixed(10)}°<br>
                    Height: ${result.height.toFixed(4)} m
                </div>
            </div>
            <hr>
            <div class="row">
                <div class="col-md-12">
                    <strong>🗺️ DMS Format:</strong><br>
                    ${result.latitude_dms}<br>
                    ${result.longitude_dms}
                </div>
            </div>
            <hr>
            <strong>⚡ Convergence:</strong> ${result.converged ? '✓' : '✗'} after ${result.total_iterations} iterations<br>
            <span class="badge bg-info">Minimum 3 iterations performed</span>
            
            <div class="mt-3">
                <strong>📊 ITERATION DETAILS (First 3 iterations):</strong>
                <div class="table-responsive">
                    <table class="table table-sm table-bordered mt-2">
                        <thead class="table-light">
                            <tr>
                                <th>Iter</th>
                                <th>Latitude (°)</th>
                                <th>Height (m)</th>
                                <th>N (m)</th>
                                <th>p (m)</th>
                                <th>sin(lat)</th>
                                <th>cos(lat)</th>
                                <th>ΔLat (")</th>
                                <th>ΔH (mm)</th>
                            </tr>
                        </thead>
                        <tbody>
    `;
    
    result.iterations.forEach(iter => {
        html += `
            <tr>
                <td>${iter.iter}</td>
                <td>${iter.lat.toFixed(10)}</td>
                <td>${iter.h.toFixed(4)}</td>
                <td>${iter.N.toFixed(2)}</td>
                <td>${iter.p ? iter.p.toFixed(2) : 'N/A'}</td>
                <td>${iter.sin_lat ? iter.sin_lat.toFixed(8) : 'N/A'}</td>
                <td>${iter.cos_lat ? iter.cos_lat.toFixed(8) : 'N/A'}</td>
                <td>${iter.delta_lat_arcsec.toFixed(8)}</td>
                <td>${iter.delta_h_mm.toFixed(4)}</td>
            </tr>
        `;
    });
    
    html += `
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
    
    output.innerHTML = html;
}

function showSample() {
    const sampleOutput = document.getElementById('sampleOutput');
    sampleOutput.style.display = 'block';
    setTimeout(() => sampleOutput.style.display = 'none', 5000);
}

async function processBatch() {
    if (!sessionId) {
        showError('batchOutput', 'Please initialize converter first! Click "Initialize Converter" in Step 1.');
        return;
    }
    
    const formData = new FormData();
    formData.append('session_id', sessionId);
    
    if (document.getElementById('uploadRadio').checked) {
        const fileInput = document.getElementById('csvFile');
        if (!fileInput.files.length) {
            showError('batchOutput', 'Please select a CSV file');
            return;
        }
        formData.append('file', fileInput.files[0]);
    } else {
        const csvData = document.getElementById('csvData').value;
        if (!csvData.trim()) {
            showError('batchOutput', 'Please paste CSV data');
            return;
        }
        const blob = new Blob([csvData], {type: 'text/csv'});
        formData.append('file', blob, 'data.csv');
    }
    
    showInfo('batchOutput', 'Processing...');
    
    try {
        console.log("Processing batch with session:", sessionId);
        
        const response = await fetch('/api/convert/batch', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        console.log("Batch response:", data);
        
        if (data.success) {
            // Add to local history
            conversionHistory = conversionHistory.concat(data.results);
            displayBatchResults(data);
        } else {
            showError('batchOutput', data.error);
        }
    } catch (error) {
        console.error("Batch error:", error);
        showError('batchOutput', error.message);
    }
}

function displayBatchResults(data) {
    const batchOutput = document.getElementById('batchOutput');
    const batchResults = document.getElementById('batchResults');
    
    batchOutput.innerHTML = `
        <div class="alert alert-success">
            ✅ Successfully processed ${data.total_processed} points with ${data.total_errors} errors<br>
            <span class="badge bg-info">Minimum 3 iterations performed for each point</span>
            <br><small>Total conversions in history: ${conversionHistory.length}</small>
        </div>
    `;
    
    if (data.errors && data.errors.length > 0) {
        batchOutput.innerHTML += `
            <div class="alert alert-warning">
                <strong>Errors:</strong><br>
                ${data.errors.join('<br>')}
            </div>
        `;
    }
    
    if (data.results && data.results.length > 0) {
        let html = `
            <div class="card mt-3">
                <div class="card-header">
                    <h6>📊 SUMMARY TABLE</h6>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-striped table-hover">
                            <thead>
                                <tr>
                                    <th>Point</th>
                                    <th>X (m)</th>
                                    <th>Y (m)</th>
                                    <th>Z (m)</th>
                                    <th>Latitude (°)</th>
                                    <th>Longitude (°)</th>
                                    <th>Height (m)</th>
                                    <th>Iter</th>
                                </tr>
                            </thead>
                            <tbody>
        `;
        
        data.results.forEach(r => {
            html += `
                <tr>
                    <td>${r.point_name}</td>
                    <td>${r.X.toLocaleString()}</td>
                    <td>${r.Y.toLocaleString()}</td>
                    <td>${r.Z.toLocaleString()}</td>
                    <td>${r.latitude.toFixed(8)}</td>
                    <td>${r.longitude.toFixed(8)}</td>
                    <td>${r.height.toFixed(3)}</td>
                    <td>${r.total_iterations}</td>
                </tr>
            `;
        });
        
        html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
        
        // Show iteration details for first point with all parameters
        if (data.results.length > 0) {
            const first = data.results[0];
            html += `
                <div class="card mt-3">
                    <div class="card-header">
                        <h6>🔍 ITERATION DETAILS (First Point - ${first.point_name})</h6>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-sm table-bordered">
                                <thead class="table-light">
                                    <tr>
                                        <th>Iter</th>
                                        <th>Latitude (°)</th>
                                        <th>Height (m)</th>
                                        <th>N (m)</th>
                                        <th>p (m)</th>
                                        <th>sin(lat)</th>
                                        <th>cos(lat)</th>
                                        <th>ΔLat (")</th>
                                        <th>ΔH (mm)</th>
                                    </tr>
                                </thead>
                                <tbody>
            `;
            
            first.iterations.slice(0, 3).forEach(iter => {
                html += `
                    <tr>
                        <td>${iter.iter}</td>
                        <td>${iter.lat.toFixed(10)}</td>
                        <td>${iter.h.toFixed(4)}</td>
                        <td>${iter.N.toFixed(2)}</td>
                        <td>${iter.p ? iter.p.toFixed(2) : 'N/A'}</td>
                        <td>${iter.sin_lat ? iter.sin_lat.toFixed(8) : 'N/A'}</td>
                        <td>${iter.cos_lat ? iter.cos_lat.toFixed(8) : 'N/A'}</td>
                        <td>${iter.delta_lat_arcsec.toFixed(8)}</td>
                        <td>${iter.delta_h_mm.toFixed(4)}</td>
                    </tr>
                `;
            });
            
            html += `
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            `;
        }
        
        batchResults.innerHTML = html;
    }
}

async function generateReport() {
    if (!sessionId) {
        showError('reportOutput', 'Please initialize converter first!');
        return;
    }
    
    if (conversionHistory.length === 0) {
        showError('reportOutput', 'No conversions performed yet! Please convert some points first.');
        return;
    }
    
    console.log("Generating report for session:", sessionId);
    console.log("Local conversion history:", conversionHistory);
    
    try {
        const response = await fetch('/api/report', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_id: sessionId})
        });
        
        const data = await response.json();
        console.log("Report response:", data);
        
        if (data.success) {
            displayReport(data.history, data.ellipsoid_params);
        } else {
            showError('reportOutput', data.error || 'Failed to generate report');
        }
    } catch (error) {
        console.error("Report error:", error);
        showError('reportOutput', error.message);
    }
}

function displayReport(history, ellipsoidParams) {
    const reportOutput = document.getElementById('reportOutput');
    
    let html = `
        <div class="card">
            <div class="card-header bg-primary text-white">
                <h5 class="mb-0">📋 COMPREHENSIVE CONVERSION REPORT</h5>
            </div>
            <div class="card-body">
                <p><strong>Report Generated:</strong> ${new Date().toLocaleString()}</p>
                <p><strong>Session ID:</strong> ${sessionId}</p>
                
                <div class="alert alert-info">
                    <h6>🌍 ELLIPSOID PARAMETERS:</h6>
                    <div class="table-responsive">
                        <table class="table table-sm table-bordered">
                            <thead class="table-light">
                                <tr>
                                    <th>Parameter</th>
                                    <th>Symbol</th>
                                    <th>Value</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td>Semi-major axis</td>
                                    <td>a</td>
                                    <td>${ellipsoidParams.a.toLocaleString()} m</td>
                                </tr>
                                <tr>
                                    <td>Flattening</td>
                                    <td>f</td>
                                    <td>${ellipsoidParams.f}</td>
                                </tr>
                                <tr>
                                    <td>Inverse flattening</td>
                                    <td>1/f</td>
                                    <td>${(1/ellipsoidParams.f).toFixed(6)}</td>
                                </tr>
                                <tr>
                                    <td>Eccentricity²</td>
                                    <td>e²</td>
                                    <td>${ellipsoidParams.e2.toFixed(10)}</td>
                                </tr>
                                <tr>
                                    <td>Semi-minor axis</td>
                                    <td>b</td>
                                    <td>${ellipsoidParams.b.toLocaleString()} m</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <h6 class="mt-4">📊 CONVERSION RESULTS (${history.length} total conversions):</h6>
    `;
    
    history.forEach((conv, index) => {
        html += `
            <div class="card mt-3">
                <div class="card-header bg-secondary text-white">
                    <h6 class="mb-0">CONVERSION #${index + 1}: ${conv.point_name}</h6>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-4">
                            <strong>📌 INPUT (Cartesian):</strong><br>
                            X = ${conv.X.toLocaleString()} m<br>
                            Y = ${conv.Y.toLocaleString()} m<br>
                            Z = ${conv.Z.toLocaleString()} m
                        </div>
                        <div class="col-md-4">
                            <strong>📍 OUTPUT (Geodetic):</strong><br>
                            Latitude: ${conv.latitude.toFixed(10)}°<br>
                            Longitude: ${conv.longitude.toFixed(10)}°<br>
                            Height: ${conv.height.toFixed(4)} m
                        </div>
                        <div class="col-md-4">
                            <strong>🗺️ DMS Format:</strong><br>
                            ${conv.latitude_dms}<br>
                            ${conv.longitude_dms}
                        </div>
                    </div>
                    
                    <div class="mt-3 p-2 bg-light rounded">
                        <strong>⚡ Convergence Information:</strong><br>
                        Status: ${conv.converged ? '✓ Converged' : '✗ Did not converge'}<br>
                        Total Iterations: ${conv.total_iterations} (Minimum 3 enforced)
                    </div>
                    
                    <div class="mt-3">
                        <strong>📈 COMPLETE ITERATION DETAILS (${conv.all_iterations.length} iterations):</strong>
                        <div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
                            <table class="table table-sm table-bordered mt-2">
                                <thead class="table-light sticky-top">
                                    <tr>
                                        <th>Iter</th>
                                        <th>Latitude (°)</th>
                                        <th>Lat (rad)</th>
                                        <th>Height (m)</th>
                                        <th>N (m)</th>
                                        <th>p (m)</th>
                                        <th>sin(lat)</th>
                                        <th>cos(lat)</th>
                                        <th>ΔLat (rad)</th>
                                        <th>ΔLat (")</th>
                                        <th>ΔH (m)</th>
                                        <th>ΔH (mm)</th>
                                    </tr>
                                </thead>
                                <tbody>
        `;
        
        conv.all_iterations.forEach(iter => {
            html += `
                <tr>
                    <td>${iter.iter}</td>
                    <td>${iter.lat.toFixed(10)}</td>
                    <td>${iter.lat_rad ? iter.lat_rad.toFixed(10) : 'N/A'}</td>
                    <td>${iter.h.toFixed(4)}</td>
                    <td>${iter.N ? iter.N.toFixed(2) : 'N/A'}</td>
                    <td>${iter.p ? iter.p.toFixed(2) : 'N/A'}</td>
                    <td>${iter.sin_lat ? iter.sin_lat.toFixed(8) : 'N/A'}</td>
                    <td>${iter.cos_lat ? iter.cos_lat.toFixed(8) : 'N/A'}</td>
                    <td>${iter.delta_lat ? iter.delta_lat.toExponential(4) : '0'}</td>
                    <td>${iter.delta_lat_arcsec ? iter.delta_lat_arcsec.toFixed(8) : '0'}</td>
                    <td>${iter.delta_h ? iter.delta_h.toExponential(4) : '0'}</td>
                    <td>${iter.delta_h_mm ? iter.delta_h_mm.toFixed(4) : '0'}</td>
                </tr>
            `;
        });
        
        html += `
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    html += `
            </div>
        </div>
    `;
    
    reportOutput.innerHTML = html;
}

function printReport() {
    if (!sessionId) {
        showError('reportOutput', 'Please initialize converter first!');
        return;
    }
    
    if (conversionHistory.length === 0) {
        showError('reportOutput', 'No conversions performed yet! Please convert some points first.');
        return;
    }
    
    // Show loading message
    showInfo('reportOutput', 'Preparing report for printing...');
    
    // First generate the report to get the data
    fetch('/api/report', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: sessionId})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Create print window with optimized layout
            createPrintWindow(data.history, data.ellipsoid_params);
        } else {
            showError('reportOutput', data.error || 'Failed to generate report');
        }
    })
    .catch(error => {
        console.error("Print error:", error);
        showError('reportOutput', error.message);
    });
}

function createPrintWindow(history, ellipsoidParams) {
    // Create a new window
    const printWindow = window.open('', '_blank');
    
    // Get current date and time
    const now = new Date();
    const dateStr = now.toLocaleDateString();
    const timeStr = now.toLocaleTimeString();
    
    // Start building the HTML content
    let html = `
    <!DOCTYPE html>
    <html>
    <head>
        <title>Geodetic Conversion Report</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            @page {
                size: landscape;
                margin: 1cm;
            }
            body { 
                padding: 20px; 
                font-family: 'Courier New', monospace;
                font-size: 10pt;
            }
            .report-header { 
                text-align: center; 
                margin-bottom: 20px;
                page-break-after: avoid;
            }
            .report-header h1 {
                font-size: 18pt;
                margin-bottom: 5px;
            }
            .report-header p {
                margin: 2px 0;
                font-size: 10pt;
            }
            .ellipsoid-table {
                width: 100%;
                margin-bottom: 20px;
                page-break-after: avoid;
            }
            .ellipsoid-table th, .ellipsoid-table td {
                padding: 4px;
                font-size: 9pt;
            }
            .conversion-section {
                page-break-inside: avoid;
                margin-bottom: 20px;
                border: 1px solid #ddd;
                padding: 10px;
                border-radius: 5px;
            }
            .conversion-header {
                background-color: #f0f0f0;
                padding: 8px;
                margin: -10px -10px 10px -10px;
                border-radius: 5px 5px 0 0;
                font-weight: bold;
                font-size: 11pt;
            }
            .coordinates-table {
                width: 100%;
                margin-bottom: 15px;
                font-size: 9pt;
            }
            .coordinates-table td {
                padding: 3px;
            }
            .iteration-table {
                width: 100%;
                font-size: 8pt;
                border-collapse: collapse;
            }
            .iteration-table th {
                background-color: #e0e0e0;
                padding: 4px;
                text-align: center;
                font-weight: bold;
                border: 1px solid #999;
            }
            .iteration-table td {
                padding: 3px;
                text-align: right;
                border: 1px solid #ccc;
            }
            .iteration-table td:first-child {
                text-align: center;
                font-weight: bold;
            }
            .iteration-table tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            .convergence-info {
                margin-top: 10px;
                padding: 5px;
                background-color: #f5f5f5;
                border-left: 4px solid #28a745;
                font-size: 9pt;
            }
            .page-break {
                page-break-before: always;
            }
            @media print {
                body { margin: 0; }
                .conversion-section { 
                    break-inside: avoid-page;
                }
            }
        </style>
    </head>
    <body>
        <div class="report-header">
            <h1>Cartesian to Geodetic Conversion Report</h1>
            <p><strong>Generated:</strong> ${dateStr} at ${timeStr}</p>
            <p><strong>Session ID:</strong> ${sessionId}</p>
            <p class="text-muted">MINIMUM 3 ITERATIONS FOR ALL POINTS - COMPLETE ITERATION DETAILS</p>
        </div>
    `;
    
    // Add Ellipsoid Parameters
    html += `
        <div class="ellipsoid-table">
            <table class="table table-bordered table-sm">
                <tr style="background-color: #007bff; color: white;">
                    <th colspan="2" style="text-align: center;">🌍 ELLIPSOID PARAMETERS</th>
                </tr>
                <tr>
                    <th style="width: 50%;">Semi-major axis (a)</th>
                    <td>${ellipsoidParams.a.toLocaleString()} m</td>
                </tr>
                <tr>
                    <th>Flattening (f)</th>
                    <td>${ellipsoidParams.f}</td>
                </tr>
                <tr>
                    <th>1/f</th>
                    <td>${(1/ellipsoidParams.f).toFixed(6)}</td>
                </tr>
                <tr>
                    <th>Eccentricity² (e²)</th>
                    <td>${ellipsoidParams.e2.toFixed(10)}</td>
                </tr>
                <tr>
                    <th>Semi-minor axis (b)</th>
                    <td>${ellipsoidParams.b.toLocaleString()} m</td>
                </tr>
            </table>
        </div>
    `;
    
    // Add each conversion
    history.forEach((conv, index) => {
        html += `
        <div class="conversion-section">
            <div class="conversion-header">
                CONVERSION #${index + 1}: ${conv.point_name}
            </div>
            
            <table class="coordinates-table">
                <tr>
                    <td style="width: 33%;"><strong>📌 INPUT:</strong></td>
                    <td style="width: 33%;"><strong>📍 OUTPUT:</strong></td>
                    <td style="width: 34%;"><strong>🗺️ DMS:</strong></td>
                </tr>
                <tr>
                    <td>X = ${conv.X.toLocaleString()} m</td>
                    <td>Lat: ${conv.latitude.toFixed(10)}°</td>
                    <td>${conv.latitude_dms}</td>
                </tr>
                <tr>
                    <td>Y = ${conv.Y.toLocaleString()} m</td>
                    <td>Lon: ${conv.longitude.toFixed(10)}°</td>
                    <td>${conv.longitude_dms}</td>
                </tr>
                <tr>
                    <td>Z = ${conv.Z.toLocaleString()} m</td>
                    <td>H: ${conv.height.toFixed(4)} m</td>
                    <td></td>
                </tr>
            </table>
            
            <div class="convergence-info">
                <strong>⚡ Convergence:</strong> ${conv.converged ? '✓ Converged' : '✗ Did not converge'} | 
                <strong>Total Iterations:</strong> ${conv.total_iterations} (Minimum 3 enforced)
            </div>
            
            <table class="iteration-table">
                <thead>
                    <tr>
                        <th>Iter</th>
                        <th>Latitude (°)</th>
                        <th>Lat (rad)</th>
                        <th>Height (m)</th>
                        <th>N (m)</th>
                        <th>p (m)</th>
                        <th>sin(lat)</th>
                        <th>cos(lat)</th>
                        <th>ΔLat (rad)</th>
                        <th>ΔLat (")</th>
                        <th>ΔH (m)</th>
                        <th>ΔH (mm)</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        // Add all iterations
        conv.all_iterations.forEach(iter => {
            html += `
                <tr>
                    <td>${iter.iter}</td>
                    <td>${iter.lat.toFixed(8)}</td>
                    <td>${iter.lat_rad ? iter.lat_rad.toFixed(8) : 'N/A'}</td>
                    <td>${iter.h.toFixed(3)}</td>
                    <td>${iter.N ? iter.N.toFixed(1) : 'N/A'}</td>
                    <td>${iter.p ? iter.p.toFixed(1) : 'N/A'}</td>
                    <td>${iter.sin_lat ? iter.sin_lat.toFixed(6) : 'N/A'}</td>
                    <td>${iter.cos_lat ? iter.cos_lat.toFixed(6) : 'N/A'}</td>
                    <td>${iter.delta_lat ? iter.delta_lat.toExponential(2) : '0'}</td>
                    <td>${iter.delta_lat_arcsec ? iter.delta_lat_arcsec.toFixed(4) : '0'}</td>
                    <td>${iter.delta_h ? iter.delta_h.toExponential(2) : '0'}</td>
                    <td>${iter.delta_h_mm ? iter.delta_h_mm.toFixed(2) : '0'}</td>
                </tr>
            `;
        });
        
        html += `
                </tbody>
            </table>
        </div>
        `;
    });
    
    // Close the HTML
    html += `
        <div style="text-align: center; margin-top: 20px; font-size: 8pt; color: #666;">
            <p>End of Report - ${history.length} conversion(s) total</p>
        </div>
    </body>
    </html>
    `;
    
    // Write to the new window
    printWindow.document.write(html);
    printWindow.document.close();
    
    // Wait for content to load then print
    setTimeout(() => {
        printWindow.print();
    }, 500);
}

async function saveToCSV() {
    if (!sessionId) {
        showError('reportOutput', 'Please initialize converter first!');
        return;
    }
    
    if (conversionHistory.length === 0) {
        showError('reportOutput', 'No results to save! Please convert some points first.');
        return;
    }
    
    console.log("Exporting CSV for session:", sessionId);
    
    try {
        const response = await fetch('/api/export/csv', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_id: sessionId})
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `conversion_results_detailed_${new Date().getTime()}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            showSuccess('reportOutput', '✅ Detailed CSV file downloaded successfully');
        } else {
            const data = await response.json();
            showError('reportOutput', data.error || 'Failed to export CSV');
        }
    } catch (error) {
        console.error("Export error:", error);
        showError('reportOutput', error.message);
    }
}

async function clearResults() {
    if (!sessionId) {
        // Just clear local display
        document.getElementById('reportOutput').innerHTML = '';
        document.getElementById('singleOutput').innerHTML = '';
        document.getElementById('batchResults').innerHTML = '';
        document.getElementById('batchOutput').innerHTML = '';
        conversionHistory = [];
        return;
    }
    
    try {
        const response = await fetch('/api/clear', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_id: sessionId})
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Clear all displays
            document.getElementById('reportOutput').innerHTML = '';
            document.getElementById('singleOutput').innerHTML = '';
            document.getElementById('batchResults').innerHTML = '';
            document.getElementById('batchOutput').innerHTML = '';
            conversionHistory = [];
            showSuccess('reportOutput', '✅ Results cleared');
        }
    } catch (error) {
        console.error("Clear error:", error);
        showError('reportOutput', error.message);
    }
}

// Utility functions
function showError(elementId, message) {
    const element = document.getElementById(elementId);
    element.innerHTML = `<div class="alert alert-danger">❌ ${message}</div>`;
    element.style.display = 'block';
}

function showSuccess(elementId, message) {
    const element = document.getElementById(elementId);
    element.innerHTML = `<div class="alert alert-success">${message}</div>`;
    element.style.display = 'block';
}

function showInfo(elementId, message) {
    const element = document.getElementById(elementId);
    element.innerHTML = `<div class="alert alert-info">ℹ️ ${message}</div>`;
    element.style.display = 'block';
}