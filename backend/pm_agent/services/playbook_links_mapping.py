"""
Hardcoded link mappings for the Project Management Playbook.
This ensures all links are properly associated with their URLs.
"""
PLAYBOOK_LINKS_MAPPING = {
    # Section 3
    "Link to Forsys Project Execution Methodology": None,
    
    # Section 4.2
    "Kick Off Deck": None,
    "Kickoff Deck": None,
    
    # Section 4.3, 4.9.6, 5.2.3, 5.2.4, 5.3.2, 5.3.3, 5.4.1, 5.4.2, 6.3.2, 6.3.3, 6.4.1, 6.4.2
    "Link to standard documentation/templates": None,
    
    # Section 4.5
    "Here is the link to Project Plan": None,
    "link to Project Plan": None,
    "Project Plan": None,
    
    # Section 4.9.6
    "Weekly Status Report Template": None,
    "=Weekly Status Report Template": None,
    
    # Section 5.3.2, 6.3.2
    "MOM Template": None,
    
    # Section 5.3.3, 5.4.2, 6.3.3, 6.4.2
    "RAID Log": None,
    "Project RAID log": None,
    "Update the Project RAID log": None,
    
    # Section 5.5.4, 6.1.11, 7.1.11, 8.2.4, 8.2.5, 9.2.6, 9.2.7, 10.1.4
    "Link to the Checklist to be completed": None,
    
    # Section 6.1.1
    "Link to the sample design plan": None,
    "sample design plan": None,
    
    # Section 6.1.4, 6.1.5
    "Link to sample design document": "https://docs.google.com/spreadsheets/d/1Gg4W2tmwaWqFQHpTqFxk3EVdWVuLKFrz/edit?usp=sharing&ouid=101935984536383661546&rtpof=true&sd=true",
    "sample design document": "https://docs.google.com/spreadsheets/d/1Gg4W2tmwaWqFQHpTqFxk3EVdWVuLKFrz/edit?usp=sharing&ouid=101935984536383661546&rtpof=true&sd=true",
    
    # Section 6.4.1
    "SDD Template": None,
    
    # Section 6.6.8
    "High Level Test Scenarios": None,
    
    # Section 7.1.4
    "Unit Testing Guidelines": "https://docs.google.com/spreadsheets/d/1yXVi8k2BtYXLIFSO_ItIabigvgHEPuoQ/edit?usp=sharing&ouid=101935984536383661546&rtpof=true&sd=true",
    "Follow the Unit Testing Guidelines": "https://docs.google.com/spreadsheets/d/1yXVi8k2BtYXLIFSO_ItIabigvgHEPuoQ/edit?usp=sharing&ouid=101935984536383661546&rtpof=true&sd=true",
    
    # Section 7.1.4
    "Configuration Log - FILE": None,
    "Configuration Log": None,
    
    # Section 7.1.5
    "Gate check Document": None,
    "Refer the gate check template": None,
    "Gate check template": None,
    
    # Section 7.1.7
    "Dependency tracker": "https://docs.google.com/spreadsheets/d/199GLTQ9TM8ZCGZaGlF-wIXzwbL_bomcOtuTfLt-jnPM/edit?usp=sharing",
    
    # Section 7.1.10
    "Sprint Closure Report Document Reference": "https://docs.google.com/spreadsheets/d/1JRcGdffDuhFScljF4RC0qFI78FoB-TXv8InXEIWA6SA/edit?usp=sharing",
    "Sprint Closure Report": "https://docs.google.com/spreadsheets/d/1JRcGdffDuhFScljF4RC0qFI78FoB-TXv8InXEIWA6SA/edit?usp=sharing",
    
    # Section 7.1.11, 8.2.5, 9.2.7
    "SIT Cutover Plan": "https://docs.google.com/spreadsheets/d/1pwft6r0YzIIEUaT8KfKKMguYpQpgp1e7/edit?usp=sharing&ouid=101935984536383661546&rtpof=true&sd=true",
    "UAT Cutover Plan": "https://docs.google.com/spreadsheets/d/1pwft6r0YzIIEUaT8KfKKMguYpQpgp1e7/edit?usp=sharing&ouid=101935984536383661546&rtpof=true&sd=true",
    "Production Cutover Plan": "https://docs.google.com/spreadsheets/d/1pwft6r0YzIIEUaT8KfKKMguYpQpgp1e7/edit?usp=sharing&ouid=101935984536383661546&rtpof=true&sd=true",
    
    # Section 8.2.4, 9.2.6, 10.1.4
    "Deployment Tracker for the SIT Deployment": "https://docs.google.com/spreadsheets/d/1q-MtmyFXa1isSzC51wiusqfpy7iKFAfZe3PxDtXhyK4/edit?usp=sharing",
    "Deployment Tracker for the UAT Deployment": "https://docs.google.com/spreadsheets/d/1q-MtmyFXa1isSzC51wiusqfpy7iKFAfZe3PxDtXhyK4/edit?usp=sharing",
    "Deployment Tracker - Production Deployment": "https://docs.google.com/spreadsheets/d/1q-MtmyFXa1isSzC51wiusqfpy7iKFAfZe3PxDtXhyK4/edit?usp=sharing",
    "Deployment Tracker": "https://docs.google.com/spreadsheets/d/1q-MtmyFXa1isSzC51wiusqfpy7iKFAfZe3PxDtXhyK4/edit?usp=sharing",
    
    # Section 10.3.3
    "CSAT Survey Link": None,
    
    # Section 10.4
    "Link to Project Closure Template": None,
    "Project Closure Template": None,
    
    # Section 11
    "Link to the documentation": None,
    
    # TDD Reference
    "TDD Reference Document": None,
    "TDD Reference Document -": None,
}

def get_link_url(link_text):
    """
    Get the URL for a given link text from the playbook mapping.
    Returns the URL if found, None otherwise.
    """
    if not link_text:
        return None
    
    # Try exact match first
    if link_text in PLAYBOOK_LINKS_MAPPING:
        return PLAYBOOK_LINKS_MAPPING[link_text]
    
    # Try case-insensitive match
    link_text_lower = link_text.strip().lower()
    for key, url in PLAYBOOK_LINKS_MAPPING.items():
        if key.lower() == link_text_lower:
            return url
    
    # Try partial match (if link text contains the key)
    for key, url in PLAYBOOK_LINKS_MAPPING.items():
        if key and key.lower() in link_text_lower:
            return url
    
    return None

def enrich_text_with_links(text):
    """
    Enrich text by replacing link text patterns with formatted links.
    This ensures playbook links are properly formatted.
    """
    if not text:
        return text
    
    enriched_text = text
    
    # Sort by length (longest first) to avoid partial replacements
    sorted_links = sorted(
        [(k, v) for k, v in PLAYBOOK_LINKS_MAPPING.items() if v], 
        key=lambda x: len(x[0]), 
        reverse=True
    )
    
    # Replace link texts with formatted versions if URLs are available
    for link_text, url in sorted_links:
        if url and link_text:
            # Format: "link_text (url)"
            formatted_link = f"{link_text} ({url})"
            
            # Try exact match first
            if link_text in enriched_text:
                enriched_text = enriched_text.replace(link_text, formatted_link)
            else:
                # Try case-insensitive replacement
                import re
                pattern = re.compile(re.escape(link_text), re.IGNORECASE)
                if pattern.search(enriched_text):
                    enriched_text = pattern.sub(formatted_link, enriched_text, count=1)
    
    return enriched_text

