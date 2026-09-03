import re
import os

with open("README.md", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Rename and reframe the opening
new_opening = """# GridGuard Voice Escalation Agent

**Explainable grid forecasting with approval-gated, disclosed CALL-E voice escalation.**

[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)](#streamlit-interface)
[![Flask](https://img.shields.io/badge/API-Flask-000000)](#flask-api)
[![XGBoost](https://img.shields.io/badge/Forecast-XGBoost-189AB4)](#forecasting-and-model-governance)
[![Data](https://img.shields.io/badge/Data-Synthetic%20%7C%20Kaggle%20%7C%20EIA-1565C0)](#three-source-data-architecture)
[![RAG](https://img.shields.io/badge/RAG-Local_TF--IDF-5E35B1)](#local-rag)
[![PostgreSQL](https://img.shields.io/badge/Persistence-PostgreSQL-336791)](#persistence)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E)](#railway-deployment)

GridGuard Voice Escalation Agent uses an XGBoost machine-learning pipeline to forecast electricity demand and identify critical grid risks. When a high-risk hour is detected, the internal expert system grounds the alert in local policy using RAG and presents a recommended escalation path.

The human operator reviews the evidence and must explicitly approve any action. If approved, the official CALL-E Python SDK creates and waits for a structured call result.

By default, the application runs in a safe dry-run preview mode. No real call is made in the public demo, ensuring the agent remains a safe, verifiable reference pattern for human-in-the-loop escalation.

---"""

content = re.sub(r"# GridGuard AI.*?---", new_opening, content, flags=re.DOTALL, count=1)


# 2. Extract and Move “Voice Escalation & CALL-E Integration”
# It's at the end of the file.
voice_sec_match = re.search(r"(## Voice Escalation & CALL-E Integration.*?)(?=\n## |\Z)", content, flags=re.DOTALL)
if voice_sec_match:
    voice_content = voice_sec_match.group(1)
    # Remove it from its original location
    content = content.replace(voice_content, "")
    
    # Insert it directly after Project Links
    links_pattern = r"(## Project Links.*?\n---)"
    new_links = r"\1\n\n" + voice_content + "\n\n---"
    content = re.sub(links_pattern, new_links, content, flags=re.DOTALL, count=1)
    
# 3. Improve Product Walkthrough
old_walkthrough_pattern = r"## Product walkthrough.*?---"
new_walkthrough = """## Product walkthrough

*Screens 05–07 demonstrate dry-run preview. No real phone call was placed.*

| Control Tower & Forecast | Multi-Agent Debate Committee |
|:---:|:---:|
| ![Control Tower](docs/images/01_control_tower.png)<br><sub>**01 Forecast Evidence** — critical forecast and operator decision.</sub> | ![Debate Committee](docs/images/02_debate_committee.png)<br><sub>**02 Committee Transcript** — analyst, compliance, and dispatcher reasoning is advisory and traceable.</sub> |

| Scenario Lab Stress Testing | Architecture & Data Sources |
|:---:|:---:|
| ![Scenario Lab](docs/images/03_scenario_lab.png)<br><sub>**03 Scenario Lab** — reproducible extreme-grid-stress simulation.</sub> | ![Data Sources](docs/images/04_data_sources.png)<br><sub>**04 Data Sources** — Synthetic, Kaggle, and EIA data normalized to one schema.</sub> |

| Voice Escalation Overview | Safety Gates & Consent |
|:---:|:---:|
| ![Voice Escalation](docs/images/05_voice_escalation_overview.png)<br><sub>**05 Voice Escalation** — critical risk produces a draft, not an automatic call.</sub> | ![Safety Gates](docs/images/06_voice_escalation_safety_gates.png)<br><sub>**06 Safety Gates** — disclosure, dry-run default, and two confirmations.</sub> |

| Escalation Result Packet | CALL-E Architecture |
|:---:|:---:|
| ![Dry Run Result](docs/images/07_dry_run_escalation_result.png)<br><sub>**07 Dry-Run Result** — structured escalation packet; no real call placed.</sub> | ![CALL-E Architecture](docs/images/08_call_e_architecture.png)<br><sub>**08 CALL-E Architecture** — risk → human approval → CALL-E SDK/API → structured audit packet.</sub> |

![Public Deployment](docs/images/09_public_railway_deployment.png)
<br><sub>**09 Public Railway Deployment** — public Railway URL proves the reviewer-accessible app is live.</sub>

---"""

content = re.sub(old_walkthrough_pattern, new_walkthrough, content, flags=re.DOTALL, count=1)

# 4. Remove duplicated content cleanly.
sections = re.split(r'(^##\s+.*?$)', content, flags=re.MULTILINE)
seen = set()
deduped_content = sections[0]
for i in range(1, len(sections), 2):
    heading = sections[i]
    body = sections[i+1]
    norm_heading = heading.strip().lower()
    
    if norm_heading in seen and norm_heading in [
        "## project structure", "## screenshots for the portfolio", 
        "## testing", "## production roadmap", "## limitations and safety"
    ]:
        continue # skip duplicate
        
    if norm_heading == "## screenshots for the portfolio":
        if "01_control_tower" not in body and "assets" in body.lower():
            continue # skip obsolete placeholders
            
    seen.add(norm_heading)
    deduped_content += heading + body

content = deduped_content

# 5. Improve readability and hierarchy
content = content.replace("# Three-source data architecture", "## Three-source data architecture")
content = content.replace("Optional Groq, or Gemini providers", "Optional Groq or Gemini providers")

feature_row = "| Voice | Approval-gated CALL-E voice escalation with dry-run default | Completed |\n"
content = re.sub(r"(\| UI \| Streamlit grid-operations control tower \| Completed \|)", r"\1\n" + feature_row, content)

pr_link = "- **CALL-E community PR:** https://github.com/CALLE-AI/awesome-phone-call-agents/pull/301"
content = content.replace("- **Portfolio:** https://draculess99.github.io/", "- **Portfolio:** https://draculess99.github.io/\n" + pr_link)

# 6. Diagrams
# Note: Keep the compact vertical CALL-E architecture diagram as the primary.
# Put the large Detailed component view Mermaid diagram inside a collapsible <details>.
detailed_pattern = r"(### Detailed component view\n\n```mermaid.*?```)"
collapsed = """<details>
<summary>Full platform architecture (optional detail)</summary>

\\1

</details>"""
content = re.sub(detailed_pattern, collapsed, content, flags=re.DOTALL)

# Ensure no empty newlines at end of file, fix trailing spaces
content = re.sub(r'\n{3,}', '\n\n', content)

with open("README.md", "w", encoding="utf-8") as f:
    f.write(content)
print("done")
