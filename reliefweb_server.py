"""
Flask server for ReliefWeb document fetcher
Provides API endpoints for fetching disaster reports, downloading PDFs,
and processing PDF text extraction.
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

app = Flask(__name__)
CORS(app)

# Global state
download_status = {}
download_files = {}
process_status = {}  # Track PDF processing jobs
countries_cache = None  # Cache for countries list


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
                            'filename': safe_filename,
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


def process_pdfs_background(job_id, folder_path):
    """Background task to process PDFs and extract text"""
    try:
        from pdf_processor import process_pdfs

        process_status[job_id] = {
            'status': 'processing',
            'progress': 0,
            'message': 'Starting PDF text extraction...',
            'total_articles': 0,
            'articles_with_pdf': 0,
            'articles_without_pdf': 0
        }

        # Find the source JSON and PDF directory
        folder = folder_path
        pdf_dir = os.path.join(folder, 'pdfs')

        # Find the JSON file in the folder
        json_files = [f for f in os.listdir(folder) if f.endswith('_reports.json')]
        if not json_files:
            raise RuntimeError(f"No *_reports.json file found in {folder}")

        source_json = os.path.join(folder, json_files[0])

        # Output path: same folder, with _full_text suffix
        base_name = json_files[0].replace('_reports.json', '')
        output_json = os.path.join(folder, f"{base_name}_reports_full_text.json")

        print(f"[{job_id}] Processing PDFs in: {pdf_dir}")
        print(f"[{job_id}] Source JSON: {source_json}")
        print(f"[{job_id}] Output JSON: {output_json}")

        def progress_callback(percent, message):
            process_status[job_id].update({
                'progress': percent,
                'message': message
            })

        result = process_pdfs(
            source_json_path=source_json,
            pdf_directory=pdf_dir,
            output_json_path=output_json,
            progress_callback=progress_callback
        )

        process_status[job_id] = {
            'status': 'completed',
            'progress': 100,
            'message': 'PDF processing complete!',
            'total_articles': result.get('total_articles', 0),
            'articles_with_pdf': result.get('articles_with_pdf', 0),
            'articles_without_pdf': result.get('articles_without_pdf', 0),
            'total_pdfs_processed': result.get('total_pdfs_processed', 0),
            'matching_statistics': result.get('matching_statistics', {}),
            'output_path': result.get('output_path', ''),
            'output_filename': os.path.basename(result.get('output_path', ''))
        }

        print(f"[{job_id}] COMPLETED - {result.get('total_articles', 0)} articles processed")

    except Exception as e:
        print(f"[{job_id}] ERROR: {e}")
        import traceback
        traceback.print_exc()
        process_status[job_id] = {
            'status': 'error',
            'progress': 0,
            'message': f'Error: {str(e)}'
        }


# ============================================================
# FETCH ENDPOINTS
# ============================================================

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
    print(f"Disaster: {disaster_name}")
    print(f"Country: {country_name} ({country_code})")
    print(f"Output: {output_dir}")
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
    """Get status of a download job"""
    if job_id not in download_status:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(download_status[job_id])


@app.route('/api/download/zip/<job_id>', methods=['GET'])
def download_zip(job_id):
    """Download the ZIP file of PDFs"""
    if job_id not in download_files:
        return jsonify({'error': 'Job files not found'}), 404

    files = download_files[job_id]
    zip_path = files.get('zip_path')

    if not zip_path or not os.path.exists(zip_path):
        return jsonify({'error': 'ZIP file not found'}), 404

    return send_file(
        zip_path,
        as_attachment=True,
        download_name=files.get('zip_filename', 'documents.zip')
    )


@app.route('/api/download/json/<job_id>', methods=['GET'])
def download_json(job_id):
    """Download the JSON metadata file"""
    if job_id not in download_files:
        return jsonify({'error': 'Job files not found'}), 404

    files = download_files[job_id]
    json_path = files.get('json_path')

    if not json_path or not os.path.exists(json_path):
        return jsonify({'error': 'JSON file not found'}), 404

    return send_file(
        json_path,
        as_attachment=True,
        download_name=files.get('json_filename', 'reports.json')
    )


# ============================================================
# PDF PROCESSING ENDPOINTS
# ============================================================

@app.route('/api/folders', methods=['GET'])
def list_folders():
    """List available data folders inside reliefweb_data"""
    output_dir = request.args.get('base_dir', './reliefweb_data')

    if not os.path.exists(output_dir):
        return jsonify([])

    folders = []
    for entry in sorted(os.listdir(output_dir)):
        entry_path = os.path.join(output_dir, entry)
        if os.path.isdir(entry_path):
            # Check if it has a pdfs subfolder and a JSON file
            has_pdfs = os.path.isdir(os.path.join(entry_path, 'pdfs'))
            json_files = [f for f in os.listdir(entry_path) if f.endswith('_reports.json')]
            has_json = len(json_files) > 0

            # Count PDFs
            pdf_count = 0
            pdf_dir = os.path.join(entry_path, 'pdfs')
            if os.path.isdir(pdf_dir):
                pdf_count = len([f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')])

            # Check if already processed
            full_text_files = [f for f in os.listdir(entry_path) if f.endswith('_full_text.json')]
            already_processed = len(full_text_files) > 0

            folders.append({
                'name': entry,
                'path': os.path.abspath(entry_path),
                'has_pdfs': has_pdfs,
                'has_json': has_json,
                'pdf_count': pdf_count,
                'json_file': json_files[0] if json_files else None,
                'already_processed': already_processed,
                'full_text_file': full_text_files[0] if full_text_files else None
            })

    return jsonify(folders)


@app.route('/api/process', methods=['POST'])
def process_pdfs_endpoint():
    """Start PDF text extraction in background"""
    data = request.json
    folder_path = data.get('folder_path')

    if not folder_path:
        return jsonify({'error': 'Missing folder_path parameter'}), 400

    if not os.path.exists(folder_path):
        return jsonify({'error': f'Folder not found: {folder_path}'}), 404

    job_id = f"process_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"\n{'='*70}")
    print(f"NEW PROCESS JOB: {job_id}")
    print(f"Folder: {folder_path}")
    print(f"{'='*70}\n")

    thread = threading.Thread(
        target=process_pdfs_background,
        args=(job_id, folder_path),
        daemon=True
    )
    thread.start()

    return jsonify({'job_id': job_id})


@app.route('/api/process/status/<job_id>', methods=['GET'])
def get_process_status(job_id):
    """Get status of a PDF processing job"""
    if job_id not in process_status:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(process_status[job_id])


@app.route('/api/process/download/<job_id>', methods=['GET'])
def download_processed_json(job_id):
    """Download the processed full-text JSON file"""
    if job_id not in process_status:
        return jsonify({'error': 'Job not found'}), 404

    status = process_status[job_id]
    output_path = status.get('output_path', '')

    if not output_path or not os.path.exists(output_path):
        return jsonify({'error': 'Output file not found'}), 404

    return send_file(
        output_path,
        as_attachment=True,
        download_name=status.get('output_filename', 'processed.json')
    )


# ============================================================
# UTILITY ENDPOINTS
# ============================================================

@app.route('/api/countries', methods=['GET'])
def get_countries():
    """Get complete list of countries from ReliefWeb API (cached)"""
    global countries_cache

    if countries_cache is not None:
        return jsonify(countries_cache)

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
        countries_cache = countries

        print(f"Loaded {len(countries)} countries from ReliefWeb API")
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


if __name__ == '__main__':
    print("\n" + "="*70)
    print("ReliefWeb Document Fetcher - Backend Server")
    print("="*70)
    print("Server starting on http://localhost:5000")
    print("Press CTRL+C to stop")
    print("="*70 + "\n")

    app.run(debug=True, port=5000, threaded=True)
