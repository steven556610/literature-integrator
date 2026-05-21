import os
import json
from processors.llm_analyzer import analyze_paper

test_paper = {
    'paper_id': '2303.08774',
    'title': 'GPT-4 Technical Report',
    'authors': 'OpenAI',
    'published_date': '2023-03-15',
    'summary': 'We report the development of GPT-4, a large-scale, multimodal model which can accept image and text inputs and produce text outputs.',
    'url': 'https://arxiv.org/abs/2303.08774',
    'source': 'arxiv',
}

backends = ['gemini', 'qwen7b']

for b in backends:
    print(f'\n--- Testing backend: {b} ---')
    try:
        res = analyze_paper(test_paper, backend=b, retries=1)
        print(f'Status: {res.get("status")}')
        if res.get("status") != 'analyzed':
            print(f'Error details: {res.get("raw_analysis")}')
    except Exception as e:
        print(f'Exception: {e}')
