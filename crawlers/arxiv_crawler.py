import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import urllib.parse
import time

# XML Namespaces for arXiv Atom feed
NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    "arxiv": "http://arxiv.org/schemas/atom"
}

def clean_text(text):
    """Remove extra whitespaces and newlines."""
    if not text:
        return ""
    return " ".join(text.split())

def parse_arxiv_xml(xml_content):
    """Parse the arXiv Atom XML feed into a list of paper dictionaries."""
    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        print(f"[!] Error parsing XML: {e}")
        return []

    papers = []
    for entry in root.findall("atom:entry", NAMESPACES):
        # Extract arXiv ID
        raw_id_url = entry.find("atom:id", NAMESPACES).text
        # e.g., http://arxiv.org/abs/2103.00021v1
        raw_id = raw_id_url.split("/abs/")[-1]
        # Canonical ID (strip version v1, v2 etc.)
        paper_id = raw_id.split("v")[0]

        title = clean_text(entry.find("atom:title", NAMESPACES).text)
        
        # Summary/Abstract
        summary = clean_text(entry.find("atom:summary", NAMESPACES).text)
        
        # Date
        published_str = entry.find("atom:published", NAMESPACES).text
        # Parse YYYY-MM-DD
        published_date = published_str.split("T")[0]
        
        # Authors
        authors_list = []
        for author in entry.findall("atom:author", NAMESPACES):
            name = author.find("atom:name", NAMESPACES).text
            authors_list.append(name)
        authors = ", ".join(authors_list)
        
        # PDF and Abstract URLs
        abs_url = raw_id_url
        pdf_url = ""
        for link in entry.findall("atom:link", NAMESPACES):
            rel = link.attrib.get("rel")
            title_attr = link.attrib.get("title")
            if rel == "related" and title_attr == "pdf":
                pdf_url = link.attrib.get("href")
            elif rel == "alternate" and not pdf_url:
                # Fallback if specific pdf link not found
                href = link.attrib.get("href")
                if "pdf" in href:
                    pdf_url = href
                    
        if not pdf_url:
            pdf_url = abs_url.replace("/abs/", "/pdf/") + ".pdf"

        papers.append({
            "paper_id": paper_id,
            "title": title,
            "authors": authors,
            "published_date": published_date,
            "summary": summary,
            "url": abs_url,
            "source": "arxiv"
        })
        
    return papers

def query_arxiv(query_str, max_results=50, start=0, sort_by="submittedDate", sort_order="descending"):
    """Fetch papers from the arXiv API matching a search query."""
    encoded_query = urllib.parse.quote(query_str)
    url = f"http://export.arxiv.org/api/query?search_query={encoded_query}&start={start}&max_results={max_results}&sortBy={sort_by}&sortOrder={sort_order}"
    
    print(f"[*] Querying arXiv: start={start}, max={max_results}...")
    headers = {"User-Agent": "LiteratureIntegrator/1.0 (steven955348@gmail.com)"}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            return parse_arxiv_xml(response.content)
        else:
            print(f"[!] arXiv API returned status code: {response.status_code}")
            return []
    except Exception as e:
        print(f"[!] Error querying arXiv: {e}")
        return []

def get_biotech_ai_query():
    """Build the intersection query between Biotech (Drugs/Vaccines) and AI/ML/NLP."""
    biotech_terms = [
        'ti:"cancer vaccine" OR abs:"cancer vaccine"',
        'ti:"drug discovery" OR abs:"drug discovery"',
        'ti:"drug design" OR abs:"drug design"',
        'ti:"neoantigen" OR abs:"neoantigen"',
        'ti:"immunotherapy" OR abs:"immunotherapy"'
    ]
    ai_terms = [
        'ti:"machine learning" OR abs:"machine learning"',
        'ti:"deep learning" OR abs:"deep learning"',
        'ti:"artificial intelligence" OR abs:"artificial intelligence"',
        'ti:"natural language processing" OR abs:"natural language processing"',
        'ti:"large language model" OR abs:"large language model"',
        'ti:"transformer" OR abs:"transformer"'
    ]
    
    biotech_query = f"({') OR ('.join(biotech_terms)})"
    ai_query = f"({') OR ('.join(ai_terms)})"
    
    return f"({biotech_query}) AND ({ai_query})"

def fetch_arxiv_papers(years_list=None, max_results=100, daily_mode=False):
    """
    Fetch relevant papers.
    In daily_mode: fetches latest and filters for papers published in last 7 days.
    Else: fetches historical matching years.
    """
    query = get_biotech_ai_query()
    papers = []
    
    if daily_mode:
        print("[*] Running arXiv Crawler in DAILY mode...")
        # Get latest papers (sorted by submission date, descending)
        raw_papers = query_arxiv(query, max_results=50, sort_by="submittedDate", sort_order="descending")
        
        # Filter for the last 7 days
        today = datetime.today()
        seven_days_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        
        for paper in raw_papers:
            if paper["published_date"] >= seven_days_ago:
                papers.append(paper)
        print(f"[*] arXiv Daily Crawler found {len(papers)} papers from the last 7 days.")
    else:
        print(f"[*] Running arXiv Crawler in HISTORICAL mode for years: {years_list}...")
        # Paginate to fetch historical papers
        batch_size = 50
        start = 0
        while len(papers) < max_results:
            batch = query_arxiv(query, max_results=batch_size, start=start, sort_by="submittedDate", sort_order="descending")
            if not batch:
                break
                
            # Filter by target years
            filtered_batch = []
            for paper in batch:
                pub_year = paper["published_date"].split("-")[0]
                if years_list is None or pub_year in years_list:
                    filtered_batch.append(paper)
            
            papers.extend(filtered_batch)
            start += batch_size
            
            # Rate limiting compliance: sleep 3 seconds
            time.sleep(3)
            
            # If the last fetched batch was empty or smaller than batch_size, we've reached the end
            if len(batch) < batch_size:
                break
                
        # Limit to max results requested
        papers = papers[:max_results]
        print(f"[*] arXiv Historical Crawler retrieved {len(papers)} papers total.")
        
    return papers

if __name__ == "__main__":
    # Test query
    test_papers = fetch_arxiv_papers(years_list=["2025", "2026"], max_results=5)
    print(f"[*] Test retrieved {len(test_papers)} papers:")
    for p in test_papers:
        print(f"  - [{p['published_date']}] {p['title']} ({p['paper_id']})")
