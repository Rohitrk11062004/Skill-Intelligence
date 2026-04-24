"""Verify all skills from the reference image land in correct categories.

Updated to match §B.2: Problem Solving → Behavioral Skills.
"""
import re

SKILL_CATEGORIES = ["Technical Skills","Domain/Tools/Process","Team Management","People Management Skills","Communication Skills","Behavioral Skills"]

CANONICAL_NAMES = {
    "git":"Git","github":"GitHub","gitlab":"GitLab","svn":"SVN","bitbucket":"Bitbucket",
    "ocr":"OCR","nlp":"NLP","ml":"Machine Learning","llms":"Large Language Models",
    "fine tuning":"Fine-tuning","fine-tuning":"Fine-tuning","finetuning":"Fine-tuning",
    "asr":"ASR","tts":"TTS",
    "reactjs":"React","react js":"React","react.js":"React",
    "gcp":"Google Cloud",
    "jira":"JIRA","jenkins":"Jenkins","postman":"Postman","swagger":"Swagger",
    "confluence":"Confluence","ci/cd":"CI/CD","cicd":"CI/CD",
    "ms excel":"MS Excel","microsoft excel":"MS Excel","excel":"MS Excel",
    "ms word":"MS Word","microsoft word":"MS Word","word":"MS Word",
    "ms powerpoint":"MS PowerPoint","powerpoint":"MS PowerPoint",
    "ms office":"MS Office",
    "objective c":"Objective C","objective-c":"Objective C",
    "view controllers":"View Controllers",
    "offline storage":"Offline Storage",
    "multi-threading":"Multi-threading","multithreading":"Multi-threading",
    "memory management":"Memory Management",
    "data models":"Data Models",
    "source code management":"Source Code Management","scm":"Source Code Management",
    "agile":"Agile","agile process":"Agile Process",
    "scrum":"Scrum",
    "knowledge on svn":"SVN",
    "decision making":"Decision Making","decision-making":"Decision Making",
    "problem solving":"Problem Solving","problem-solving":"Problem Solving",
    "developing team members":"Developing Team Members",
    "feedback - giving":"Feedback - Giving","feedback giving":"Feedback - Giving",
    "feedback - receiving":"Feedback - Receiving","feedback receiving":"Feedback - Receiving",
    "test link":"TestLink","testlink":"TestLink",
    # §A.2/C additions
    "conversation ai":"Conversational AI","conversational ai":"Conversational AI",
    "conversational workflows":"Conversational AI",
    "api integration":"API Integration","api integrations":"API Integration",
    "gen ai":"Generative AI","genai":"Generative AI",
    "gen ai frameworks":"Generative AI Frameworks",
}

FORCED_CATEGORY = {
    # Technical Skills
    "Objective C":"Technical Skills","Swift":"Technical Skills",
    "View Controllers":"Technical Skills","Multi-threading":"Technical Skills",
    "Offline Storage":"Technical Skills","Memory Management":"Technical Skills",
    "Data Models":"Technical Skills","Source Code Management":"Technical Skills",
    "Agile":"Technical Skills","Agile Process":"Technical Skills","Scrum":"Technical Skills",
    "React":"Technical Skills","Google Cloud":"Technical Skills",
    "OCR":"Technical Skills","NLP":"Technical Skills","Machine Learning":"Technical Skills",
    "Large Language Models":"Technical Skills","Fine-tuning":"Technical Skills",
    "ASR":"Technical Skills","TTS":"Technical Skills",
    "Docker":"Technical Skills","Kubernetes":"Technical Skills",
    "Conversational AI":"Technical Skills","Generative AI":"Technical Skills",
    "Generative AI Frameworks":"Technical Skills",
    "API Integration":"Technical Skills","API Development":"Technical Skills",
    # Domain/Tools/Process
    "JIRA":"Domain/Tools/Process","TestLink":"Domain/Tools/Process",
    "Jenkins":"Domain/Tools/Process","SVN":"Domain/Tools/Process",
    "Git":"Domain/Tools/Process","GitHub":"Domain/Tools/Process",
    "GitLab":"Domain/Tools/Process","Bitbucket":"Domain/Tools/Process",
    "CI/CD":"Domain/Tools/Process","Confluence":"Domain/Tools/Process",
    "Postman":"Domain/Tools/Process","Swagger":"Domain/Tools/Process",
    "MS Excel":"Domain/Tools/Process","MS Word":"Domain/Tools/Process",
    "MS PowerPoint":"Domain/Tools/Process","MS Office":"Domain/Tools/Process",
    # Team Management
    "Delegation":"Team Management",
    "Clarity":"Team Management","Decision Making":"Team Management",
    "Technical Leadership":"Team Management",
    # People Management Skills
    "Developing Team Members":"People Management Skills",
    "Commitment":"People Management Skills",
    "Feedback - Giving":"People Management Skills",
    "Feedback - Receiving":"People Management Skills",
    "Mentoring":"People Management Skills","Coaching":"People Management Skills",
    "Onboarding":"People Management Skills","Hiring":"People Management Skills",
    # Communication Skills
    "Active Listening":"Communication Skills",
    "Verbal Communication":"Communication Skills",
    "Stakeholder Communication":"Communication Skills",
    "Presentation Skills":"Communication Skills",
    "Documentation":"Communication Skills",
    # Behavioral Skills  (Problem Solving moved here per §B.2)
    "Problem Solving":"Behavioral Skills",
    "Adaptability":"Behavioral Skills","Ownership":"Behavioral Skills",
}

DROP_LIST = {
    "coding","code","architecture","product architecture","product design","deployment",
    "communication","communication skills","troubleshooting","debugging","testing",
    "maintenance","bug fixes","service delivery","project delivery",
    "team members","pipelines","conversational workflows","solutions",
    "best practices","industry standards","cross-functional teams",
}

DROP_LEADING_VERBS = {
    "implement","build","develop","architect","design","deliver","deploy","collaborate",
    "work","participate","conduct","write","review","optimize","oversee","evaluate",
}

def normalize_and_recategorize(skills):
    result = []
    seen = set()
    for s in skills:
        name = str(s.get("name","")).strip()
        if not name: continue
        canonical = CANONICAL_NAMES.get(name.lower(), name)
        if canonical == name and not any(c.isupper() for c in name[1:]):
            canonical = name.title()
        if canonical.lower() in DROP_LIST: continue
        if len(canonical.split()) > 6: continue
        if canonical.split()[0].lower() in DROP_LEADING_VERBS: continue
        proposed = s.get("category","Technical Skills")
        final = FORCED_CATEGORY.get(canonical, proposed)
        if final not in SKILL_CATEGORIES: final = "Technical Skills"
        dk = canonical.lower().replace(" ","").replace("-","").replace(".","").replace("/","")
        if dk in seen: continue
        seen.add(dk)
        result.append({"name":canonical,"category":final})
    return result

# ═══ TEST: Every skill from the reference image + new §B requirements ═════════

test_input = [
    # --- Technical Skills (from image) ---
    {"name":"Objective C",           "category":"Technical Skills"},
    {"name":"Swift",                 "category":"Technical Skills"},
    {"name":"View Controllers",      "category":"Technical Skills"},
    {"name":"Multi-threading",       "category":"Technical Skills"},
    {"name":"offline storage",       "category":"Technical Skills"},
    {"name":"Memory Management",     "category":"Technical Skills"},
    {"name":"Data Models",           "category":"Technical Skills"},
    {"name":"Source Code Management", "category":"Domain/Tools/Process"},
    {"name":"Agile process",         "category":"Domain/Tools/Process"},

    # --- Domain/Tools/Process (from image) ---
    {"name":"JIRA",                  "category":"Technical Skills"},
    {"name":"Test Link",             "category":"Technical Skills"},
    {"name":"Jenkins",               "category":"Technical Skills"},
    {"name":"Knowledge on SVN",      "category":"Technical Skills"},

    # --- Team Management (from image) ---
    {"name":"Delegation",            "category":"Behavioral Skills"},
    {"name":"Clarity",               "category":"Communication Skills"},
    {"name":"Decision making",       "category":"Behavioral Skills"},

    # --- §B.2: Problem Solving → Behavioral Skills ---
    {"name":"Problem Solving",       "category":"Team Management"},

    # --- People Management Skills (from image) ---
    {"name":"Developing team members","category":"Team Management"},
    {"name":"Commitment",            "category":"Behavioral Skills"},
    {"name":"Feedback - Giving",     "category":"Communication Skills"},
    {"name":"Feedback - Receiving",  "category":"Communication Skills"},

    # --- Communication Skills (from image) ---
    {"name":"Active Listening",      "category":"Communication Skills"},
    {"name":"Verbal communication",  "category":"Communication Skills"},

    # --- Junk that should be dropped ---
    {"name":"Coding",                "category":"Technical Skills"},
    {"name":"Architecture",          "category":"Technical Skills"},
    {"name":"Product Architecture",  "category":"Technical Skills"},
    {"name":"Product Design",        "category":"Technical Skills"},
    {"name":"Deployment",            "category":"Technical Skills"},
    {"name":"Team Members",          "category":"People Management Skills"},
    {"name":"Conversational Workflows","category":"Technical Skills"},
    {"name":"Pipelines",             "category":"Technical Skills"},

    # --- Extra tools that must go to Domain/Tools/Process ---
    {"name":"Git",                   "category":"Technical Skills"},
    {"name":"GitHub",                "category":"Technical Skills"},
    {"name":"MS Excel",              "category":"Technical Skills"},
    {"name":"MS Word",               "category":"Technical Skills"},
    {"name":"PowerPoint",            "category":"Technical Skills"},

    # --- AI/ML that must stay Technical ---
    {"name":"OCR",                   "category":"Domain/Tools/Process"},
    {"name":"NLP",                   "category":"Domain/Tools/Process"},

    # --- §C normalization checks ---
    {"name":"React JS",              "category":"Technical Skills"},
    {"name":"Conversation AI",       "category":"Technical Skills"},
    {"name":"API integrations",      "category":"Technical Skills"},
    {"name":"gcp",                   "category":"Technical Skills"},
]

result = normalize_and_recategorize(test_input)

# ═══ DISPLAY ══════════════════════════════════════════════════════════════════
print("=" * 70)
print(f"  {'SKILL':<35s} {'CATEGORY':<25s}")
print("-" * 70)
by_cat = {}
for s in result:
    by_cat.setdefault(s["category"], []).append(s["name"])
for cat in SKILL_CATEGORIES:
    if cat in by_cat:
        print(f"\n  [{cat}]")
        for name in by_cat[cat]:
            print(f"    • {name}")
print("-" * 70)
print(f"  Input: {len(test_input)} | Output: {len(result)} | Dropped: {len(test_input)-len(result)}")
print("=" * 70)

# ═══ ASSERTIONS ═══════════════════════════════════════════════════════════════
by_name = {s["name"]: s["category"] for s in result}
names = set(by_name.keys())

# Image: Technical Skills
for skill in ["Objective C","Swift","View Controllers","Multi-threading","Offline Storage","Memory Management","Data Models","Source Code Management","Agile Process"]:
    actual_name = skill if skill in names else skill.title()
    assert actual_name in names, f"Missing: {skill} (tried {actual_name})"
    assert by_name[actual_name] == "Technical Skills", f"{actual_name} should be Technical Skills, got {by_name[actual_name]}"

# Image: Domain/Tools/Process
for skill in ["JIRA","TestLink","Jenkins","SVN"]:
    assert skill in names, f"Missing: {skill}"
    assert by_name[skill] == "Domain/Tools/Process", f"{skill} should be Domain/Tools/Process, got {by_name[skill]}"

# Image: Team Management (Problem Solving removed from here — now Behavioral)
for skill in ["Delegation","Clarity","Decision Making"]:
    assert skill in names, f"Missing: {skill}"
    assert by_name[skill] == "Team Management", f"{skill} should be Team Management, got {by_name[skill]}"

# §B.2: Problem Solving → Behavioral Skills
assert "Problem Solving" in names, "Missing: Problem Solving"
assert by_name["Problem Solving"] == "Behavioral Skills", f"Problem Solving should be Behavioral Skills, got {by_name['Problem Solving']}"

# Image: People Management Skills
for skill in ["Developing Team Members","Commitment","Feedback - Giving","Feedback - Receiving"]:
    assert skill in names, f"Missing: {skill}"
    assert by_name[skill] == "People Management Skills", f"{skill} should be People Management Skills, got {by_name[skill]}"

# Image: Communication Skills
for skill in ["Active Listening","Verbal Communication"]:
    assert skill in names, f"Missing: {skill}"
    assert by_name[skill] == "Communication Skills", f"{skill} should be Communication Skills, got {by_name[skill]}"

# Junk must be gone
for junk in ["Coding","Architecture","Product Architecture","Product Design","Deployment",
             "Team Members","Pipelines"]:
    assert junk not in names, f"'{junk}' should have been dropped"

# "Conversational Workflows" must be remapped → "Conversational AI" (Technical Skills)
assert "Conversational Workflows" not in names, "'Conversational Workflows' should not appear as-is"
assert "Conversational AI" in names, "'Conversational AI' should exist (mapped from 'Conversational Workflows')"
assert by_name["Conversational AI"] == "Technical Skills"

# Extra quality gates
assert by_name["Git"] == "Domain/Tools/Process"
assert by_name["GitHub"] == "Domain/Tools/Process"
assert by_name["Git"] == by_name["GitHub"], "Git and GitHub must be in SAME category"
assert by_name["MS Excel"] == "Domain/Tools/Process"
assert by_name["MS Word"] == "Domain/Tools/Process"
assert by_name["MS PowerPoint"] == "Domain/Tools/Process"
assert by_name["OCR"] == "Technical Skills"
assert by_name["NLP"] == "Technical Skills"

# §C normalization checks
assert "React" in names, "React JS should normalize to React"
assert "Conversational AI" in names, "Conversation AI should normalize to Conversational AI"
assert "API Integration" in names, "API integrations should normalize to API Integration"
assert "Google Cloud" in names, "gcp should normalize to Google Cloud"

print("\nALL QUALITY GATES PASSED ✓")
print("  ✓ Problem Solving → Behavioral Skills (§B.2 fix)")
print("  ✓ Git == GitHub → Domain/Tools/Process")
print("  ✓ MS Office family → Domain/Tools/Process")
print("  ✓ OCR/NLP → Technical Skills")
print("  ✓ Junk dropped: Team Members, Pipelines, Conversational Workflows")
print("  ✓ Normalization: React JS→React, Conversation AI→Conversational AI, API integrations→API Integration, gcp→Google Cloud")
