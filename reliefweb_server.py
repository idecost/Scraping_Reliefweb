"""
Flask server for ReliefWeb document fetcher
Provides API endpoints for fetching disaster reports, downloading PDFs,
and processing PDFs to extract text.
"""
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import requests
import json
import os
import zipfile
from datetime import datetime
import threading
import shutil
import tempfile
import uuid

app = Flask(__name__)
CORS(app)

# Global state
download_status = {}
download_files = {}
process_status = {}
process_files = {}

# ============================================================
# SECTION 1: Document Fetcher (existing functionality)
# ============================================================

def extract_text_content(fields):
    """Extract text content from report fields"""
    if 'body-html' in fields:
        return fields['body-html']
    elif 'body' in fields:
        return fields['body']
    return ''

def fetch_reports_background(job_id, disaster_name, country_code, country_name, output_dir):
    """Background task to fetch reports and download PDFs"""
    try:
        download_status[job_id] = {
            'status': 'fetching',
            'progress': 0,
            'message': 'Fetching report list from ReliefWeb...',
            'total_reports': 0,
            'downloaded_pdfs': 0
        }

        url = "https://api.reliefweb.int/v1/reports"
        params = {"appname": "ISI_Scraping_1234BjV0393fyHx2S2OQ"}

        payload = {
            "limit": 1000,
            "preset": "latest",
            "profile": "full",
            "filter": {
                "operator": "AND",
                "conditions": [
                    {"field": "primary_country.iso3", "value": country_code},
                    {"field": "disaster.name", "value": disaster_name},
                    {"field": "language.code", "value": "en"},
                    {"field": "format.name", "value": "Map", "negate": True}
                ]
            },
            "fields": {
                "include": [
                    "id", "title", "date", "country", "primary_country",
                    "disaster", "source", "url", "url_alias", "body", "body-html",
                    "file", "language"
                ]
            }
        }

        print(f"[{job_id}] Fetching reports for {disaster_name} in {country_name}...")

        response = requests.post(url, params=params, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        reports = data.get('data', [])
        total = len(reports)

        print(f"[{job_id}] Found {total} reports")

        download_status[job_id].update({
            'status': 'downloading',
            'total_reports': total,
            'message': f'Found {total} reports. Downloading PDFs...'
        })

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        job_output_dir = os.path.join(output_dir, f"{disaster_name.replace(' ', '_')}_{country_code}_{timestamp}")
        pdf_dir = os.path.join(job_output_dir, "pdfs")
        os.makedirs(pdf_dir, exist_ok=True)

        results = []
        total_pdfs = 0

        for i, report in enumerate(reports, 1):
            fields = report.get('fields', {})
            report_id = report.get('id', '')

            print(f"[{job_id}] Processing {i}/{total}: {fields.get('title', 'Untitled')[:60]}...")

            report_data = {
                'reliefweb_id': report_id,
                'title': fields.get('title', ''),
                'date': fields.get('date', {}),
                'url': fields.get('url_alias', ''),
                'body_text': extract_text_content(fields),
                'source': [s.get('name', '') for s in fields.get('source', [])],
                'files': []
            }

            files = fields.get('file', [])
            for file_info in files:
                file_url = file_info.get('url', '')
                filename = file_info.get('filename', 'document.pdf')

                if 'pdf' in filename.lower() and file_url:
                    try:
                        print(f"[{job_id}]   Downloading: {filename}")

                        pdf_response = requests.get(file_url, timeout=120)
                        pdf_response.raise_for_status()

                        safe_filename = f"{report_id}_{filename}"
                        safe_filename = "".join(c for c in safe_filename if c.isalnum() or c in ('_', '-', '.'))
                        pdf_path = os.path.join(pdf_dir, safe_filename)

                        with open(pdf_path, 'wb') as f:
                            f.write(pdf_response.content)

                        print(f"[{job_id}]   Saved: {safe_filename} ({len(pdf_response.content)} bytes)")

                        report_data['files'].append({
                            'saved_filename': safe_filename,
                            'filename': filename,
                            'path': pdf_path,
                            'url': file_url,
                            'size': len(pdf_response.content)
                        })

                        total_pdfs += 1

                    except Exception as e:
                        print(f"[{job_id}]   Error downloading {filename}: {e}")

            results.append(report_data)

            progress = int((i / total) * 90)
            download_status[job_id].update({
                'progress': progress,
                'downloaded_pdfs': total_pdfs,
                'message': f'Processed {i}/{total} reports, downloaded {total_pdfs} PDFs...'
            })

        download_status[job_id].update({
            'progress': 90,
            'message': 'Creating JSON metadata file...'
        })

        json_filename = f"{disaster_name.replace(' ', '_')}_{country_code}_reports.json"
        json_path = os.path.join(job_output_dir, json_filename)

        json_data = {
            'disaster': disaster_name,
            'country': country_name,
            'country_code': country_code,
            'total_documents': len(results),
            'total_pdfs': total_pdfs,
            'fetched_on': datetime.now().isoformat(),
            'reports': results
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        print(f"[{job_id}] JSON saved: {json_path}")

        download_status[job_id].update({
            'progress': 95,
            'message': 'Creating ZIP file...'
        })

        zip_filename = f"{disaster_name.replace(' ', '_')}_{country_code}_pdfs.zip"
        zip_path = os.path.join(job_output_dir, zip_filename)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for result in results:
                for file_info in result['files']:
                    if os.path.exists(file_info['path']):
                        zipf.write(file_info['path'], os.path.basename(file_info['path']))
            zipf.write(json_path, json_filename)

        print(f"[{job_id}] ZIP created: {zip_path}")

        download_files[job_id] = {
            'json_path': json_path,
            'zip_path': zip_path,
            'output_dir': job_output_dir,
            'json_filename': json_filename,
            'zip_filename': zip_filename
        }

        download_status[job_id] = {
            'status': 'completed',
            'progress': 100,
            'message': 'Download complete!',
            'total_reports': len(results),
            'downloaded_pdfs': total_pdfs,
            'output_dir': job_output_dir
        }

        print(f"[{job_id}] COMPLETED - {total_pdfs} PDFs from {len(results)} reports")

    except Exception as e:
        print(f"[{job_id}] ERROR: {e}")
        import traceback
        traceback.print_exc()
        download_status[job_id] = {
            'status': 'error',
            'progress': 0,
            'message': f'Error: {str(e)}'
        }


# ============================================================
# SECTION 2: PDF Text Processor (upload & process)
# ============================================================

def process_uploaded_pdfs_background(job_id, upload_dir, pdf_files_info, json_data):
    """Background task to process uploaded PDFs using pdf_processor logic."""
    try:
        from pdf_processor import extract_text_from_pdf, match_pdf_to_report
        from pathlib import Path

        total_pdfs = len(pdf_files_info)
        reports = json_data.get('reports', []) if json_data else []

        process_status[job_id] = {
            'status': 'processing',
            'progress': 5,
            'message': f'Starting text extraction from {total_pdfs} PDFs...',
            'total_pdfs': total_pdfs,
            'processed': 0
        }

        # Build output structure (same as pdf_processor.process_pdfs)
        emdat_event = json_data.get('emdat_event', {}) if json_data else {}

        output = {
            "DisNo": emdat_event.get('DisNo', ''),
            "disaster_type": emdat_event.get('disaster_type', json_data.get('disaster', '') if json_data else ''),
            "country": emdat_event.get('country', json_data.get('country', '') if json_data else ''),
            "iso2": emdat_event.get('iso2', json_data.get('country_code', '') if json_data else ''),
            "location": emdat_event.get('location', ''),
            "start_dt": emdat_event.get('start_dt', ''),
            "query": emdat_event.get('query', json_data.get('disaster', '') if json_data else ''),
            "articles": []
        }

        pdf_tables_collection = []
        matching_stats = {
            "exact_match": 0, "partial_match": 0, "id_match": 0,
            "reliefweb_id_match": 0, "title_match": 0, "no_match": 0
        }

        for idx, pdf_info in enumerate(pdf_files_info):
            pdf_path = Path(pdf_info['path'])
            pdf_filename = pdf_info['original_name']
            percent = 10 + int((idx / max(total_pdfs, 1)) * 70)

            process_status[job_id].update({
                'progress': percent,
                'message': f'Processing PDF {idx + 1}/{total_pdfs}: {pdf_filename[:50]}...',
                'processed': idx + 1
            })

            pdf_text, pdf_tables = extract_text_from_pdf(pdf_path)

            if pdf_tables:
                pdf_tables_collection.append({
                    "pdf_filename": pdf_filename,
                    "tables": pdf_tables
                })

            matched_report = match_pdf_to_report(pdf_filename, reports)

            article = {
                "pdf_filename": pdf_filename,
                "has_pdf": True,
                "pdf_text": pdf_text,
                "pdf_text_length": len(pdf_text)
            }

            if matched_report:
                files = matched_report.get('files', [])
                exact = False
                for fi in files:
                    sf = fi.get('saved_filename', '') or fi.get('filename', '')
                    if sf.lower() == pdf_filename.lower():
                        exact = True
                        matching_stats["exact_match"] += 1
                        break
                if not exact:
                    pdf_parts = pdf_filename.replace('.pdf', '').split('_')
                    if len(pdf_parts) >= 1 and pdf_parts[0] == str(matched_report.get('reliefweb_id', '')):
                        matching_stats["reliefweb_id_match"] += 1
                    else:
                        matching_stats["title_match"] += 1

                sources = matched_report.get('sources', matched_report.get('source', []))
                if isinstance(sources, list) and sources and isinstance(sources[0], dict):
                    source_names = [s.get('name', '') for s in sources]
                else:
                    source_names = sources if isinstance(sources, list) else []

                language = matched_report.get('language', {})
                language_name = language.get('name', '') if isinstance(language, dict) else str(language)
                date_info = matched_report.get('date', {})

                article.update({
                    "title": matched_report.get('title', ''),
                    "date": {
                        "created": date_info.get('created', ''),
                        "changed": date_info.get('changed', ''),
                        "original": date_info.get('original', '')
                    },
                    "url": matched_report.get('url', ''),
                    "sources": source_names,
                    "language": language_name,
                    "body_text": matched_report.get('body_text', matched_report.get('content', {}).get('body_text', ''))
                })
            else:
                matching_stats["no_match"] += 1
                article.update({
                    "title": "", "date": {"created": "", "changed": "", "original": ""},
                    "url": "", "sources": [], "language": "", "body_text": ""
                })

            output['articles'].append(article)

        # Add reports without PDFs
        process_status[job_id].update({'progress': 85, 'message': 'Adding reports without PDFs...'})
        for report in reports:
            report_title = report.get('title', '')
            already_processed = any(a.get('title') == report_title for a in output['articles'])
            if not already_processed:
                sources = report.get('sources', report.get('source', []))
                if isinstance(sources, list) and sources and isinstance(sources[0], dict):
                    source_names = [s.get('name', '') for s in sources]
                else:
                    source_names = sources if isinstance(sources, list) else []
                language = report.get('language', {})
                language_name = language.get('name', '') if isinstance(language, dict) else str(language)
                date_info = report.get('date', {})
                article = {
                    "pdf_filename": "", "has_pdf": False, "pdf_text": "", "pdf_text_length": 0,
                    "title": report.get('title', ''),
                    "date": {"created": date_info.get('created', ''), "changed": date_info.get('changed', ''), "original": date_info.get('original', '')},
                    "url": report.get('url', report.get('url_alias', '')),
                    "sources": source_names, "language": language_name,
                    "body_text": report.get('body_text', report.get('content', {}).get('body_text', ''))
                }
                output['articles'].append(article)

        output['n_documents'] = len(output['articles'])
        output['pdf_tables'] = pdf_tables_collection
        output['processing_metadata'] = {
            "processing_date": datetime.now().isoformat(),
            "total_pdfs_found": total_pdfs,
            "total_reports": len(reports),
            "matching_statistics": matching_stats
        }

        # Save output JSON
        process_status[job_id].update({'progress': 92, 'message': 'Saving full-text JSON...'})
        output_filename = f"reports_full_text_{job_id[:20]}.json"
        output_path = os.path.join(upload_dir, output_filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        articles_with_pdf = sum(1 for a in output['articles'] if a.get('has_pdf'))
        articles_without_pdf = sum(1 for a in output['articles'] if not a.get('has_pdf'))

        process_files[job_id] = {
            'output_path': output_path,
            'output_filename': output_filename
        }

        process_status[job_id] = {
            'status': 'completed',
            'progress': 100,
            'message': 'Processing complete!',
            'total_pdfs': total_pdfs,
            'processed': total_pdfs,
            'articles_with_pdf': articles_with_pdf,
            'articles_without_pdf': articles_without_pdf,
            'total_articles': output['n_documents'],
            'matching_statistics': matching_stats
        }

        print(f"[PROCESS {job_id}] COMPLETED - {total_pdfs} PDFs processed, {output['n_documents']} articles total")

    except Exception as e:
        print(f"[PROCESS {job_id}] ERROR: {e}")
        import traceback
        traceback.print_exc()
        process_status[job_id] = {
            'status': 'error',
            'progress': 0,
            'message': f'Error: {str(e)}'
        }


# ============================================================
# API ROUTES
# ============================================================

# --- Fetch routes ---

@app.route('/api/fetch', methods=['POST'])
def fetch_reports():
    """Start fetching reports in background"""
    data = request.json
    disaster_name = data.get('disaster_name')
    country_code = data.get('country_code')
    country_name = data.get('country_name')
    output_dir = data.get('output_dir', './reliefweb_data')

    if not all([disaster_name, country_code, country_name]):
        return jsonify({'error': 'Missing required parameters'}), 400

    job_id = f"{disaster_name.replace(' ', '_')}_{country_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"\n{'='*70}")
    print(f"NEW FETCH JOB: {job_id}")
    print(f"{'='*70}\n")

    thread = threading.Thread(
        target=fetch_reports_background,
        args=(job_id, disaster_name, country_code, country_name, output_dir),
        daemon=True
    )
    thread.start()

    return jsonify({'job_id': job_id})

@app.route('/api/status/<job_id>', methods=['GET'])
def get_status(job_id):
    """Get status of a fetch job"""
    if job_id not in download_status:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(download_status[job_id])

@app.route('/api/download/zip/<job_id>', methods=['GET'])
def download_zip(job_id):
    """Download the ZIP file"""
    if job_id not in download_files:
        return jsonify({'error': 'Job files not found'}), 404
    files = download_files[job_id]
    zip_path = files.get('zip_path')
    if not zip_path or not os.path.exists(zip_path):
        return jsonify({'error': 'ZIP file not found'}), 404
    return send_file(zip_path, as_attachment=True, download_name=files.get('zip_filename', 'documents.zip'))

@app.route('/api/download/json/<job_id>', methods=['GET'])
def download_json(job_id):
    """Download the JSON metadata file"""
    if job_id not in download_files:
        return jsonify({'error': 'Job files not found'}), 404
    files = download_files[job_id]
    json_path = files.get('json_path')
    if not json_path or not os.path.exists(json_path):
        return jsonify({'error': 'JSON file not found'}), 404
    return send_file(json_path, as_attachment=True, download_name=files.get('json_filename', 'reports.json'))

# --- Process routes (PDF text extraction) ---

@app.route('/api/process', methods=['POST'])
def process_pdfs_upload():
    """
    Upload PDFs + optional metadata JSON, process them and return full-text JSON.
    Expects multipart/form-data with:
      - 'pdfs': multiple PDF files
      - 'metadata_json': optional JSON metadata file
    """
    if 'pdfs' not in request.files:
        return jsonify({'error': 'No PDF files uploaded'}), 400

    pdf_files = request.files.getlist('pdfs')
    if not pdf_files:
        return jsonify({'error': 'No PDF files uploaded'}), 400

    # Create temp directory for this job
    job_id = str(uuid.uuid4())[:12]
    upload_dir = os.path.join(tempfile.gettempdir(), f'reliefweb_process_{job_id}')
    pdf_dir = os.path.join(upload_dir, 'pdfs')
    os.makedirs(pdf_dir, exist_ok=True)

    # Save uploaded PDFs
    pdf_files_info = []
    for pdf_file in pdf_files:
        if pdf_file.filename and pdf_file.filename.lower().endswith('.pdf'):
            safe_name = pdf_file.filename
            save_path = os.path.join(pdf_dir, safe_name)
            pdf_file.save(save_path)
            pdf_files_info.append({
                'path': save_path,
                'original_name': safe_name
            })

    if not pdf_files_info:
        return jsonify({'error': 'No valid PDF files found in upload'}), 400

    # Load metadata JSON if provided
    json_data = None
    if 'metadata_json' in request.files:
        json_file = request.files['metadata_json']
        if json_file.filename:
            try:
                json_data = json.load(json_file)
            except Exception as e:
                print(f"Warning: Could not parse metadata JSON: {e}")

    print(f"\n{'='*70}")
    print(f"NEW PROCESS JOB: {job_id}")
    print(f"PDFs: {len(pdf_files_info)}, Metadata JSON: {'Yes' if json_data else 'No'}")
    print(f"{'='*70}\n")

    # Start background processing
    thread = threading.Thread(
        target=process_uploaded_pdfs_background,
        args=(job_id, upload_dir, pdf_files_info, json_data),
        daemon=True
    )
    thread.start()

    return jsonify({'job_id': job_id, 'total_pdfs': len(pdf_files_info)})

@app.route('/api/process/status/<job_id>', methods=['GET'])
def get_process_status(job_id):
    """Get status of a processing job"""
    if job_id not in process_status:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(process_status[job_id])

@app.route('/api/process/download/<job_id>', methods=['GET'])
def download_process_result(job_id):
    """Download the full-text JSON result"""
    if job_id not in process_files:
        return jsonify({'error': 'Job files not found'}), 404
    files = process_files[job_id]
    output_path = files.get('output_path')
    if not output_path or not os.path.exists(output_path):
        return jsonify({'error': 'Output file not found'}), 404
    return send_file(output_path, as_attachment=True, download_name=files.get('output_filename', 'full_text.json'))

# --- Common routes ---

@app.route('/api/countries', methods=['GET'])
def get_countries():
    """Get list of countries from ReliefWeb API"""
    try:
        url = "https://api.reliefweb.int/v1/countries"
        params = {
            "appname": "ISI_Scraping_1234BjV0393fyHx2S2OQ",
            "limit": 1000,
            "fields[include][]": ["name", "iso3", "id"]
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        countries = []
        for country in data.get('data', []):
            fields = country.get('fields', {})
            iso3 = fields.get('iso3', '')
            name = fields.get('name', '')
            if iso3 and name:
                countries.append({'code': iso3, 'name': name})

        countries.sort(key=lambda x: x['name'])
        return jsonify(countries)

    except Exception as e:
        print(f"Error fetching countries: {e}")
        return jsonify([
            {'code': 'HTI', 'name': 'Haiti'},
            {'code': 'USA', 'name': 'United States'},
            {'code': 'PHL', 'name': 'Philippines'},
            {'code': 'NPL', 'name': 'Nepal'},
            {'code': 'PAK', 'name': 'Pakistan'}
        ])

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'online',
        'message': 'ReliefWeb Fetcher API is running',
        'timestamp': datetime.now().isoformat()
    })

# Serve the HTML page directly
@app.route('/')
def serve_index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'demo_standalone.html')

if __name__ == '__main__':
    print("\n" + "="*70)
    print("ReliefWeb Document Fetcher - Backend Server")
    print("="*70)
    print("Server starting on http://localhost:5000")
    print("Press CTRL+C to stop")
    print("="*70 + "\n")

    app.run(debug=True, port=5000, threaded=True)
