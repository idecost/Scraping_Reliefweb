"""
PDF Text Extraction Module
Extracts text from PDFs and builds a structured JSON output.
Excludes tables and image captions, keeping only body text.
"""

import json
import pdfplumber
from pathlib import Path
from typing import Dict, List, Any, Optional
import re
from datetime import datetime


def extract_text_from_pdf(pdf_path: Path) -> tuple:
    """
    Extract text from a PDF using pdfplumber, excluding tables and images.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        tuple: (extracted text, list of tables)
    """
    text_content = []
    all_tables = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables()

                if tables:
                    for table_idx, table in enumerate(tables):
                        if table:
                            all_tables.append({
                                "page": page_num,
                                "table_number": table_idx + 1,
                                "data": table
                            })

                page_text = page.extract_text(layout=False)

                if page_text:
                    if tables:
                        table_texts = set()
                        for table in tables:
                            if table:
                                for row in table:
                                    if row:
                                        for cell in row:
                                            if cell and isinstance(cell, str):
                                                table_texts.add(cell.strip())

                        lines = page_text.split('\n')
                        filtered_lines = []

                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue

                            words = line.split()
                            if words:
                                table_word_count = sum(1 for word in words if word.strip() in table_texts)
                                if table_word_count / len(words) > 0.5:
                                    continue

                            if re.match(
                                r'^\s*(Figure|Fig\.?|Table|Tabella|Tbl\.?|Immagine|Image|Photo|Foto)\s*\d+',
                                line, re.IGNORECASE
                            ):
                                continue

                            if re.match(r'^\s*(Source|Fonte)\s*:', line, re.IGNORECASE):
                                continue

                            filtered_lines.append(line)

                        if filtered_lines:
                            text_content.append('\n'.join(filtered_lines))
                    else:
                        lines = page_text.split('\n')
                        filtered_lines = []

                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue

                            if re.match(
                                r'^\s*(Figure|Fig\.?|Table|Tabella|Tbl\.?|Immagine|Image|Photo|Foto)\s*\d+',
                                line, re.IGNORECASE
                            ):
                                continue

                            if re.match(r'^\s*(Source|Fonte)\s*:', line, re.IGNORECASE):
                                continue

                            filtered_lines.append(line)

                        if filtered_lines:
                            text_content.append('\n'.join(filtered_lines))

    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        return "", []

    return '\n\n'.join(text_content), all_tables


def find_pdf_files(directory: Path) -> List[Path]:
    """
    Find all PDF files in a directory (including subdirectories).

    Args:
        directory: Path to the directory

    Returns:
        List[Path]: Sorted list of PDF file paths
    """
    if not directory.exists():
        print(f"Directory not found: {directory}")
        return []

    pdf_files = list(directory.glob('*.pdf'))
    pdf_files.extend(list(directory.glob('**/*.pdf')))

    return sorted(set(pdf_files))


def match_pdf_to_report(pdf_filename: str, reports: List[Dict]) -> Optional[Dict]:
    """
    Match a PDF file to its corresponding report based on filename.
    Uses the 'saved_filename' field inside 'files' for matching.

    Args:
        pdf_filename: Name of the PDF file
        reports: List of reports from the JSON

    Returns:
        Optional[Dict]: Matching report or None
    """
    pdf_name_lower = pdf_filename.lower()

    # Pass 1: exact match on saved_filename
    for report in reports:
        files = report.get('files', [])
        for file_info in files:
            saved_filename = file_info.get('saved_filename', '') or file_info.get('filename', '')
            if saved_filename and saved_filename.lower() == pdf_name_lower:
                return report

    # Pass 2: match without extension
    for report in reports:
        files = report.get('files', [])
        for file_info in files:
            saved_filename = file_info.get('saved_filename', '') or file_info.get('filename', '')
            if saved_filename:
                saved_base = saved_filename.replace('.pdf', '').lower()
                pdf_base = pdf_name_lower.replace('.pdf', '').lower()
                if saved_base == pdf_base:
                    return report

    # Pass 3: match using ID prefix
    pdf_parts = pdf_filename.replace('.pdf', '').split('_')
    if len(pdf_parts) >= 2:
        pdf_id_prefix = f"{pdf_parts[0]}_{pdf_parts[1]}"
        for report in reports:
            files = report.get('files', [])
            for file_info in files:
                saved_filename = file_info.get('saved_filename', '') or file_info.get('filename', '')
                if saved_filename and saved_filename.lower().startswith(pdf_id_prefix.lower()):
                    return report

    # Pass 4: match using reliefweb_id
    if len(pdf_parts) >= 1:
        potential_id = pdf_parts[0]
        for report in reports:
            reliefweb_id = str(report.get('reliefweb_id', ''))
            if reliefweb_id and reliefweb_id == potential_id:
                return report

    # Pass 5: partial title match (fallback)
    base_name = pdf_filename.replace('.pdf', '').lower()
    if len(pdf_parts) >= 3:
        base_name_no_id = '_'.join(pdf_parts[2:]).lower()
    else:
        base_name_no_id = base_name

    for report in reports:
        if 'title' in report:
            title_normalized = re.sub(r'[^a-z0-9]+', '', report['title'].lower())
            name_normalized = re.sub(r'[^a-z0-9]+', '', base_name_no_id)
            if len(name_normalized) > 10:
                if name_normalized in title_normalized or title_normalized in name_normalized:
                    return report

    return None


def process_pdfs(source_json_path: str, pdf_directory: str, output_json_path: str,
                 progress_callback=None) -> Dict[str, Any]:
    """
    Main processing function. Extracts text from PDFs and builds structured JSON.

    Args:
        source_json_path: Path to the source JSON metadata file
        pdf_directory: Path to the directory containing PDFs
        output_json_path: Path where the output JSON will be saved
        progress_callback: Optional callback(percent, message) for progress updates

    Returns:
        Dict with processing results summary
    """
    source_json_path = Path(source_json_path)
    pdf_directory = Path(pdf_directory)
    output_json_path = Path(output_json_path)

    def report_progress(percent, message):
        if progress_callback:
            progress_callback(percent, message)
        print(f"  [{percent}%] {message}")

    report_progress(0, "Loading source JSON...")

    # Load source JSON
    try:
        with open(source_json_path, 'r', encoding='utf-8') as f:
            source_data = json.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load source JSON: {e}")

    # Extract base info
    emdat_event = source_data.get('emdat_event', {})

    output = {
        "DisNo": emdat_event.get('DisNo', ''),
        "disaster_type": emdat_event.get('disaster_type', source_data.get('disaster', '')),
        "country": emdat_event.get('country', source_data.get('country', '')),
        "iso2": emdat_event.get('iso2', source_data.get('country_code', '')),
        "location": emdat_event.get('location', ''),
        "start_dt": emdat_event.get('start_dt', ''),
        "query": emdat_event.get('query', source_data.get('disaster', '')),
        "articles": []
    }

    # Find PDFs
    report_progress(5, "Scanning for PDF files...")
    pdf_files = find_pdf_files(pdf_directory)
    total_pdfs = len(pdf_files)
    report_progress(10, f"Found {total_pdfs} PDF files")

    reports = source_data.get('reports', [])

    # Process each PDF
    pdf_tables_collection = []
    matching_stats = {
        "exact_match": 0,
        "partial_match": 0,
        "id_match": 0,
        "reliefweb_id_match": 0,
        "title_match": 0,
        "no_match": 0
    }

    for idx, pdf_path in enumerate(pdf_files):
        percent = 10 + int((idx / max(total_pdfs, 1)) * 70)
        report_progress(percent, f"Processing PDF {idx + 1}/{total_pdfs}: {pdf_path.name[:50]}...")

        pdf_text, pdf_tables = extract_text_from_pdf(pdf_path)

        if pdf_tables:
            pdf_tables_collection.append({
                "pdf_filename": pdf_path.name,
                "tables": pdf_tables
            })

        matched_report = match_pdf_to_report(pdf_path.name, reports)

        article = {
            "pdf_filename": pdf_path.name,
            "has_pdf": True,
            "pdf_text": pdf_text,
            "pdf_text_length": len(pdf_text)
        }

        if matched_report:
            # Determine match type for stats
            files = matched_report.get('files', [])
            exact = False
            for fi in files:
                sf = fi.get('saved_filename', '') or fi.get('filename', '')
                if sf.lower() == pdf_path.name.lower():
                    exact = True
                    matching_stats["exact_match"] += 1
                    break
            if not exact:
                pdf_parts = pdf_path.name.replace('.pdf', '').split('_')
                if len(pdf_parts) >= 1 and pdf_parts[0] == str(matched_report.get('reliefweb_id', '')):
                    matching_stats["reliefweb_id_match"] += 1
                else:
                    matching_stats["title_match"] += 1

            sources = matched_report.get('sources', matched_report.get('source', []))
            if isinstance(sources, list) and sources and isinstance(sources[0], dict):
                source_names = [s.get('name', '') for s in sources]
            else:
                source_names = sources if isinstance(sources, list) else []

            countries = matched_report.get('countries', [])
            if isinstance(countries, list) and countries and isinstance(countries[0], dict):
                country_names = [c.get('name', '') for c in countries]
            else:
                country_names = countries if isinstance(countries, list) else []

            disasters = matched_report.get('disasters', [])
            if isinstance(disasters, list) and disasters and isinstance(disasters[0], dict):
                disaster_names = [d.get('name', '') for d in disasters]
            else:
                disaster_names = disasters if isinstance(disasters, list) else []

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
                "title": "",
                "date": {"created": "", "changed": "", "original": ""},
                "url": "",
                "sources": [],
                "language": "",
                "body_text": ""
            })

        output['articles'].append(article)

    # Add reports without PDFs
    report_progress(82, "Adding reports without PDFs...")
    for report in reports:
        report_title = report.get('title', '')
        already_processed = any(
            article.get('title') == report_title
            for article in output['articles']
        )

        if not already_processed:
            sources = report.get('sources', report.get('source', []))
            if isinstance(sources, list) and sources and isinstance(sources[0], dict):
                source_names = [s.get('name', '') for s in sources]
            else:
                source_names = sources if isinstance(sources, list) else []

            countries = report.get('countries', [])
            if isinstance(countries, list) and countries and isinstance(countries[0], dict):
                country_names = [c.get('name', '') for c in countries]
            else:
                country_names = countries if isinstance(countries, list) else []

            disasters = report.get('disasters', [])
            if isinstance(disasters, list) and disasters and isinstance(disasters[0], dict):
                disaster_names = [d.get('name', '') for d in disasters]
            else:
                disaster_names = disasters if isinstance(disasters, list) else []

            language = report.get('language', {})
            language_name = language.get('name', '') if isinstance(language, dict) else str(language)

            date_info = report.get('date', {})

            article = {
                "pdf_filename": "",
                "has_pdf": False,
                "pdf_text": "",
                "pdf_text_length": 0,
                "title": report.get('title', ''),
                "date": {
                    "created": date_info.get('created', ''),
                    "changed": date_info.get('changed', ''),
                    "original": date_info.get('original', '')
                },
                "url": report.get('url', report.get('url_alias', '')),
                "sources": source_names,
                "countries": country_names,
                "disasters": disaster_names,
                "language": language_name,
                "body_text": report.get('body_text', report.get('content', {}).get('body_text', ''))
            }
            output['articles'].append(article)

    output['n_documents'] = len(output['articles'])
    output['pdf_tables'] = pdf_tables_collection

    output['processing_metadata'] = {
        "processing_date": datetime.now().isoformat(),
        "source_json": str(source_json_path),
        "pdf_directory": str(pdf_directory),
        "total_pdfs_found": total_pdfs,
        "total_reports": len(reports),
        "matching_statistics": matching_stats
    }

    # Save output JSON
    report_progress(90, "Saving output JSON...")
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    articles_with_pdf = sum(1 for a in output['articles'] if a.get('has_pdf'))
    articles_without_pdf = sum(1 for a in output['articles'] if not a.get('has_pdf'))

    report_progress(100, "Processing complete!")

    return {
        "output_path": str(output_json_path),
        "total_articles": output['n_documents'],
        "articles_with_pdf": articles_with_pdf,
        "articles_without_pdf": articles_without_pdf,
        "total_pdfs_processed": total_pdfs,
        "matching_statistics": matching_stats
    }
