import markdown
import re

def convert_markdown_to_html():
    try:
        with open('docs/investing.md', 'r', encoding='utf-8') as f:
            text = f.read()

        # Basic markdown conversion
        # We assume standard markdown. MathJax will handle $$ delimiters in the browser
        # as long as they aren't aggressively escaped by python-markdown.
        # To be safe, we can wrap $$ blocks in a way that preserves them,
        # but usually standard markdown ignores them or treats them as text.

        html_content = markdown.markdown(text, extensions=['tables', 'fenced_code', 'nl2br'])

        # Premium CSS and MathJax Setup
        final_html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>My Investment Philosophy</title>

<!-- MathJax for rendering formulas -->
<script>
MathJax = {{
  tex: {{
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
  }},
  svg: {{
    fontCache: 'global'
  }}
}};
</script>
<script type="text/javascript" id="MathJax-script" async
  src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js">
</script>

<!-- Google Fonts for premium typography -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&family=Noto+Serif+KR:wght@400;700&display=swap" rel="stylesheet">

<!-- GitHub Markdown CSS as base -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown-light.min.css">

<style>
    body {{
        background-color: #f9f9f9;
        font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        line-height: 1.8;
        color: #24292f;
    }}

    .markdown-body {{
        box-sizing: border-box;
        min-width: 200px;
        max-width: 900px;
        margin: 40px auto;
        padding: 60px;
        background-color: #ffffff;
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    }}

    /* Typography Adjustments */
    .markdown-body h1 {{
        font-family: 'Noto Serif KR', serif;
        border-bottom: 2px solid #24292f;
        padding-bottom: 15px;
        margin-bottom: 40px;
        font-size: 2.5em;
        text-align: center;
        font-weight: 700;
    }}

    .markdown-body h2 {{
        font-family: 'Noto Serif KR', serif;
        border-bottom: 1px solid #eaecef;
        padding-bottom: 10px;
        margin-top: 50px;
        margin-bottom: 20px;
        font-size: 1.8em;
        color: #1a1a1a;
    }}

    .markdown-body h3 {{
        margin-top: 35px;
        font-size: 1.4em;
        color: #0d47a1; /* Accent color for subheaders */
    }}

    .markdown-body p {{
        font-size: 1.05em;
        margin-bottom: 1.5em;
        word-break: keep-all; /* Improve Korean line breaking */
    }}

    /* Quote styling */
    .markdown-body blockquote {{
        border-left: 5px solid #0d47a1;
        background-color: #f5f8ff;
        padding: 15px 20px;
        color: #444;
        font-style: italic;
    }}

    /* List styling */
    .markdown-body ul, .markdown-body ol {{
        padding-left: 2em;
        margin-bottom: 1.5em;
    }}

    .markdown-body ul ul,
    .markdown-body ul ol,
    .markdown-body ol ul,
    .markdown-body ol ol {{
        margin-top: 0.5em;
        margin-bottom: 0.5em;
        padding-left: 2em; /* Explicit indentation for nested lists */
    }}

    .markdown-body li {{
        margin-bottom: 0.5em;
    }}

    .markdown-body li > p {{
        margin-bottom: 0.5em;
    }}

    /* Table styling */
    .markdown-body table {{
        display: table;
        width: 100%;
        margin: 30px 0;
        border-collapse: collapse;
        overflow: hidden;
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}

    .markdown-body th {{
        background-color: #f6f8fa;
        font-weight: 600;
        text-align: center;
    }}

    .markdown-body td {{
        padding: 12px 15px;
    }}

    @media (max-width: 767px) {{
        body {{ padding: 0; }}
        .markdown-body {{
            padding: 20px;
            margin: 0;
            border-radius: 0;
            box-shadow: none;
        }}
    }}
</style>
</head>
<body class="markdown-body">
{html_content}
</body>
</html>'''

        with open('docs/investing.html', 'w', encoding='utf-8') as f:
            f.write(final_html)

        print("HTML generation successful.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    convert_markdown_to_html()
