"""
paper_resolver.py
Accepts a user-submitted URL or DOI and returns a unified paper metadata dict.
Supports arXiv, bioRxiv, medRxiv, and generic DOI (via Crossref).
"""
import re
import requests
import time

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def clean_text(text):
    """Remove extra whitespace and newlines."""
    if not text:
        return ""
    return " ".join(text.split())


def _arxiv_id_from_url(url: str):
    """Extract canonical arXiv ID from any arxiv.org URL."""
    # Patterns: /abs/ID, /pdf/ID, /abs/ID.pdf, arxiv:ID
    patterns = [
        r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]+(?:v\d+)?)",
        r"arxiv:([0-9]{4}\.[0-9]+(?:v\d+)?)",
        r"([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)",  # bare ID
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            raw_id = m.group(1)
            # Strip version suffix (e.g. v2)
            return re.sub(r"v\d+$", "", raw_id)
    return None


def _doi_from_biorxiv_url(url: str):
    """
    Extract DOI from a bioRxiv or medRxiv URL.
    Examples:
      https://www.biorxiv.org/content/10.1101/2021.01.01.123456v2
      https://doi.org/10.1101/2021.01.01.123456
    """
    patterns = [
        r"biorxiv\.org/content/(10\.\d{4,}/[^\s?#]+)",
        r"medrxiv\.org/content/(10\.\d{4,}/[^\s?#]+)",
        r"(10\.\d{4,}/[^\s?#]+)",  # generic DOI pattern
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            doi = m.group(1)
            # Strip version suffix like v1, v2
            doi = re.sub(r"v\d+$", "", doi)
            return doi.rstrip(".")
    return None


# --------------------------------------------------------------------------- #
# arXiv resolver
# --------------------------------------------------------------------------- #

def resolve_arxiv(arxiv_id: str) -> dict | None:
    """Query arXiv API for a specific paper ID."""
    import xml.etree.ElementTree as ET

    NAMESPACES = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    headers = {"User-Agent": "LiteratureIntegrator/1.0 (steven955348@gmail.com)"}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"[!] arXiv API error {resp.status_code} for ID {arxiv_id}")
            return None

        root = ET.fromstring(resp.content)
        entry = root.find("atom:entry", NAMESPACES)
        if entry is None:
            print(f"[!] No arXiv entry found for ID {arxiv_id}")
            return None

        raw_id_url = entry.find("atom:id", NAMESPACES).text
        paper_id = raw_id_url.split("/abs/")[-1]
        paper_id = re.sub(r"v\d+$", "", paper_id)

        title = clean_text(entry.find("atom:title", NAMESPACES).text)
        summary = clean_text(entry.find("atom:summary", NAMESPACES).text)
        published_str = entry.find("atom:published", NAMESPACES).text
        published_date = published_str.split("T")[0]

        authors_list = []
        for author in entry.findall("atom:author", NAMESPACES):
            name = author.find("atom:name", NAMESPACES).text
            authors_list.append(name)
        authors = ", ".join(authors_list)

        return {
            "paper_id": paper_id,
            "title": title,
            "authors": authors,
            "published_date": published_date,
            "summary": summary,
            "url": raw_id_url,
            "source": "arxiv",
        }

    except Exception as e:
        print(f"[!] Exception resolving arXiv ID {arxiv_id}: {e}")
        return None


# --------------------------------------------------------------------------- #
# bioRxiv / medRxiv resolver (via bioRxiv content API)
# --------------------------------------------------------------------------- #

def resolve_biorxiv(doi: str) -> dict | None:
    """Fetch paper metadata from bioRxiv/medRxiv via their content API."""
    # Try bioRxiv first, then medRxiv
    headers = {"User-Agent": "LiteratureIntegrator/1.0 (steven955348@gmail.com)"}

    for server in ("biorxiv", "medrxiv"):
        url = f"https://api.biorxiv.org/details/{server}/{doi}"
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                continue

            data = resp.json()
            collection = data.get("collection", [])
            if not collection:
                continue

            # Use the latest version (last in collection list)
            item = collection[-1]

            title = clean_text(item.get("title", ""))
            authors = item.get("authors", "")
            published_date = item.get("date", "")
            summary = clean_text(item.get("abstract", ""))

            if server == "biorxiv":
                paper_url = f"https://www.biorxiv.org/content/{doi}v1"
            else:
                paper_url = f"https://www.medrxiv.org/content/{doi}v1"

            return {
                "paper_id": doi,
                "title": title,
                "authors": authors,
                "published_date": published_date,
                "summary": summary,
                "url": paper_url,
                "source": server,
            }

        except Exception as e:
            print(f"[!] Exception resolving {server} DOI {doi}: {e}")
            continue

    return None


# --------------------------------------------------------------------------- #
# Generic DOI resolver via Crossref
# --------------------------------------------------------------------------- #

def resolve_crossref(doi: str) -> dict | None:
    """Resolve a DOI via Crossref REST API — works for any publisher."""
    encoded_doi = requests.utils.quote(doi, safe="")
    url = f"https://api.crossref.org/works/{encoded_doi}"
    headers = {
        "User-Agent": "LiteratureIntegrator/1.0 (mailto:steven955348@gmail.com)"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"[!] Crossref error {resp.status_code} for DOI {doi}")
            return None

        msg = resp.json().get("message", {})

        title_list = msg.get("title", [])
        title = clean_text(title_list[0]) if title_list else "Unknown Title"

        # Authors
        author_list = msg.get("author", [])
        authors_parts = []
        for a in author_list:
            given = a.get("given", "")
            family = a.get("family", "")
            if family:
                authors_parts.append(f"{given} {family}".strip())
        authors = ", ".join(authors_parts)

        # Date
        published = msg.get("published-print") or msg.get("published-online") or msg.get("created", {})
        date_parts = published.get("date-parts", [[]])
        if date_parts and date_parts[0]:
            parts = date_parts[0]
            if len(parts) >= 3:
                published_date = f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
            elif len(parts) == 2:
                published_date = f"{parts[0]:04d}-{parts[1]:02d}-01"
            else:
                published_date = str(parts[0])
        else:
            published_date = ""

        abstract = clean_text(msg.get("abstract", ""))
        link = msg.get("URL", f"https://doi.org/{doi}")

        # Detect source from type or container
        container = msg.get("container-title", [""])[0].lower()
        source = "unknown"
        if "biorxiv" in container:
            source = "biorxiv"
        elif "medrxiv" in container:
            source = "medrxiv"

        return {
            "paper_id": doi,
            "title": title,
            "authors": authors,
            "published_date": published_date,
            "summary": abstract,
            "url": link,
            "source": source,
        }

    except Exception as e:
        print(f"[!] Exception resolving DOI via Crossref {doi}: {e}")
        return None


# --------------------------------------------------------------------------- #
# Main dispatcher
# --------------------------------------------------------------------------- #

def resolve_paper(user_input: str) -> dict | None:
    """
    Main entry point: accepts any URL, DOI string, or arXiv ID.
    Returns a unified paper metadata dict or None if resolution fails.
    """
    user_input = user_input.strip()
    print(f"[*] Resolving: {user_input}")

    # ---- arXiv ----
    if "arxiv.org" in user_input or user_input.startswith("arxiv:") or re.match(r"^\d{4}\.\d{4,5}", user_input):
        arxiv_id = _arxiv_id_from_url(user_input)
        if arxiv_id:
            print(f"[*] Detected arXiv ID: {arxiv_id}")
            return resolve_arxiv(arxiv_id)

    # ---- bioRxiv / medRxiv by URL ----
    if "biorxiv.org" in user_input or "medrxiv.org" in user_input:
        doi = _doi_from_biorxiv_url(user_input)
        if doi:
            print(f"[*] Detected bioRxiv/medRxiv DOI: {doi}")
            paper = resolve_biorxiv(doi)
            if paper:
                return paper
            # Fallback to Crossref
            return resolve_crossref(doi)

    # ---- Generic DOI (doi.org URL or bare DOI) ----
    doi_match = re.search(r"(10\.\d{4,}/[^\s?#\"'<>]+)", user_input)
    if doi_match:
        doi = doi_match.group(1).rstrip(".")
        print(f"[*] Detected generic DOI: {doi}")
        # Try bioRxiv first (it handles bioRxiv/medRxiv DOIs)
        paper = resolve_biorxiv(doi)
        if paper:
            return paper
        # Fallback to Crossref
        return resolve_crossref(doi)

    print(f"[!] Could not determine paper type from input: {user_input}")
    return None


# --------------------------------------------------------------------------- #
# CLI test
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    test_links = [
        "https://arxiv.org/abs/2303.08774",          # ChatGPT paper
        "https://www.biorxiv.org/content/10.1101/2021.07.18.452833v2",  # bioRxiv
        "10.1101/2021.07.18.452833",                 # bare DOI
    ]
    for link in test_links:
        result = resolve_paper(link)
        if result:
            print(f"\n[OK] [{result['source']}] {result['title'][:80]}")
            print(f"   Authors: {result['authors'][:60]}")
            print(f"   Date: {result['published_date']}")
        else:
            print(f"\n[FAIL] Failed to resolve: {link}")
        time.sleep(2)
