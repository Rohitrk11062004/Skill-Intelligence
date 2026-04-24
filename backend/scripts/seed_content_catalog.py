#!/usr/bin/env python3
"""Seed a static content catalog into content_items.

Usage:
    python scripts/seed_content_catalog.py
"""

import asyncio
from pathlib import Path
import sys

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import AsyncSessionLocal
from app.models.models import ContentItem


def _normalize_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    # Normalize trailing slashes for idempotent inserts.
    while value.endswith("/"):
        value = value[:-1]
    return value


RESOURCES: list[dict] = [
    # Software engineering
    {"title": "Scientific Computing with Python", "provider": "freeCodeCamp", "source_url": "https://www.freecodecamp.org/learn/scientific-computing-with-python/", "difficulty_level": "beginner", "skill_tags": ["Python"], "resource_format": "course", "duration_minutes": 600},
    {"title": "Python Tutorial", "provider": "Python Docs", "source_url": "https://docs.python.org/3/tutorial/", "difficulty_level": "beginner", "skill_tags": ["Python"], "resource_format": "doc", "duration_minutes": None},

    {"title": "FastAPI Full Course", "provider": "freeCodeCamp", "source_url": "https://www.youtube.com/watch?v=0sOvCWFmrtA", "difficulty_level": "intermediate", "skill_tags": ["FastAPI"], "resource_format": "video", "duration_minutes": 300},
    {"title": "FastAPI Tutorial", "provider": "FastAPI", "source_url": "https://fastapi.tiangolo.com/tutorial/", "difficulty_level": "intermediate", "skill_tags": ["FastAPI"], "resource_format": "doc", "duration_minutes": None},

    {"title": "JavaScript Algorithms and Data Structures", "provider": "freeCodeCamp", "source_url": "https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures-v8/", "difficulty_level": "beginner", "skill_tags": ["JavaScript"], "resource_format": "course", "duration_minutes": 600},
    {"title": "JavaScript Guide", "provider": "MDN", "source_url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide", "difficulty_level": "beginner", "skill_tags": ["JavaScript"], "resource_format": "doc", "duration_minutes": None},

    {"title": "React Course for Beginners", "provider": "freeCodeCamp", "source_url": "https://www.youtube.com/watch?v=bMknfKXIFA8", "difficulty_level": "beginner", "skill_tags": ["React"], "resource_format": "video", "duration_minutes": 720},
    {"title": "React Learn", "provider": "React", "source_url": "https://react.dev/learn", "difficulty_level": "beginner", "skill_tags": ["React"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Intro to SQL", "provider": "Khan Academy", "source_url": "https://www.khanacademy.org/computing/computer-programming/sql", "difficulty_level": "beginner", "skill_tags": ["SQL"], "resource_format": "course", "duration_minutes": 240},
    {"title": "PostgreSQL Tutorial", "provider": "PostgreSQL", "source_url": "https://www.postgresql.org/docs/current/tutorial.html", "difficulty_level": "beginner", "skill_tags": ["SQL"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Git and GitHub for Beginners", "provider": "freeCodeCamp", "source_url": "https://www.youtube.com/watch?v=RGOj5yH7evk", "difficulty_level": "beginner", "skill_tags": ["Git"], "resource_format": "video", "duration_minutes": 70},
    {"title": "Git Reference", "provider": "Git", "source_url": "https://git-scm.com/doc", "difficulty_level": "beginner", "skill_tags": ["Git"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Docker for Beginners", "provider": "freeCodeCamp", "source_url": "https://www.youtube.com/watch?v=fqMOX6JJhGo", "difficulty_level": "intermediate", "skill_tags": ["Docker"], "resource_format": "video", "duration_minutes": 180},
    {"title": "Docker Get Started", "provider": "Docker", "source_url": "https://docs.docker.com/get-started/", "difficulty_level": "intermediate", "skill_tags": ["Docker"], "resource_format": "doc", "duration_minutes": None},

    {"title": "System Design Interview Course", "provider": "freeCodeCamp", "source_url": "https://www.youtube.com/watch?v=UzLMhqg3_Wc", "difficulty_level": "advanced", "skill_tags": ["System Design"], "resource_format": "video", "duration_minutes": 150},
    {"title": "Microservices", "provider": "Martin Fowler", "source_url": "https://martinfowler.com/articles/microservices.html", "difficulty_level": "advanced", "skill_tags": ["System Design"], "resource_format": "article", "duration_minutes": None},

    # AI/ML
    {"title": "PyTorch for Deep Learning", "provider": "freeCodeCamp", "source_url": "https://www.youtube.com/watch?v=V_xro1bcAuA", "difficulty_level": "advanced", "skill_tags": ["PyTorch"], "resource_format": "video", "duration_minutes": 120},
    {"title": "PyTorch Tutorials", "provider": "PyTorch", "source_url": "https://pytorch.org/tutorials/", "difficulty_level": "advanced", "skill_tags": ["PyTorch"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Intro to Machine Learning", "provider": "Kaggle", "source_url": "https://www.kaggle.com/learn/intro-to-machine-learning", "difficulty_level": "intermediate", "skill_tags": ["scikit-learn"], "resource_format": "course", "duration_minutes": 240},
    {"title": "scikit-learn User Guide", "provider": "scikit-learn", "source_url": "https://scikit-learn.org/stable/user_guide.html", "difficulty_level": "intermediate", "skill_tags": ["scikit-learn"], "resource_format": "doc", "duration_minutes": None},

    {"title": "MLflow in Practice", "provider": "Databricks", "source_url": "https://www.youtube.com/watch?v=859OxXrt_TI", "difficulty_level": "intermediate", "skill_tags": ["MLflow"], "resource_format": "video", "duration_minutes": 55},
    {"title": "MLflow Documentation", "provider": "MLflow", "source_url": "https://mlflow.org/docs/latest/index.html", "difficulty_level": "intermediate", "skill_tags": ["MLflow"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Hugging Face Course", "provider": "Hugging Face", "source_url": "https://huggingface.co/learn/nlp-course/chapter1/1", "difficulty_level": "intermediate", "skill_tags": ["Hugging Face"], "resource_format": "course", "duration_minutes": 300},
    {"title": "Transformers Documentation", "provider": "Hugging Face", "source_url": "https://huggingface.co/docs/transformers/index", "difficulty_level": "intermediate", "skill_tags": ["Hugging Face"], "resource_format": "doc", "duration_minutes": None},

    {"title": "ChatGPT Prompt Engineering for Developers", "provider": "DeepLearning.AI", "source_url": "https://www.deeplearning.ai/short-courses/chatgpt-prompt-engineering-for-developers/", "difficulty_level": "beginner", "skill_tags": ["Prompt Engineering"], "resource_format": "course", "duration_minutes": 90},
    {"title": "Prompt Engineering Guide", "provider": "Prompting Guide", "source_url": "https://www.promptingguide.ai/", "difficulty_level": "beginner", "skill_tags": ["Prompt Engineering"], "resource_format": "doc", "duration_minutes": None},

    # Data engineering
    {"title": "dbt Fundamentals", "provider": "dbt", "source_url": "https://learn.getdbt.com/courses/fundamentals", "difficulty_level": "intermediate", "skill_tags": ["dbt"], "resource_format": "course", "duration_minutes": 240},
    {"title": "dbt Introduction", "provider": "dbt", "source_url": "https://docs.getdbt.com/docs/introduction", "difficulty_level": "intermediate", "skill_tags": ["dbt"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Airflow 101", "provider": "Astronomer", "source_url": "https://academy.astronomer.io/path/airflow-101", "difficulty_level": "intermediate", "skill_tags": ["Airflow"], "resource_format": "course", "duration_minutes": 180},
    {"title": "Airflow Tutorial", "provider": "Apache Airflow", "source_url": "https://airflow.apache.org/docs/apache-airflow/stable/tutorial/index.html", "difficulty_level": "intermediate", "skill_tags": ["Airflow"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Apache Spark Full Course", "provider": "freeCodeCamp", "source_url": "https://www.youtube.com/watch?v=_C8kWso4ne4", "difficulty_level": "advanced", "skill_tags": ["Spark"], "resource_format": "video", "duration_minutes": 240},
    {"title": "Spark Quick Start", "provider": "Apache Spark", "source_url": "https://spark.apache.org/docs/latest/quick-start.html", "difficulty_level": "advanced", "skill_tags": ["Spark"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Data Modeling in Data Warehouses", "provider": "DataCamp", "source_url": "https://www.datacamp.com/courses/data-modeling-in-sql", "difficulty_level": "advanced", "skill_tags": ["Data Modeling"], "resource_format": "course", "duration_minutes": 180},
    {"title": "What is Data Modeling?", "provider": "IBM", "source_url": "https://www.ibm.com/think/topics/data-modeling", "difficulty_level": "advanced", "skill_tags": ["Data Modeling"], "resource_format": "article", "duration_minutes": None},

    # Data science
    {"title": "Pandas", "provider": "Kaggle", "source_url": "https://www.kaggle.com/learn/pandas", "difficulty_level": "beginner", "skill_tags": ["pandas"], "resource_format": "course", "duration_minutes": 180},
    {"title": "Pandas Getting Started", "provider": "pandas", "source_url": "https://pandas.pydata.org/docs/getting_started/index.html", "difficulty_level": "beginner", "skill_tags": ["pandas"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Statistics and Probability", "provider": "Khan Academy", "source_url": "https://www.khanacademy.org/math/statistics-probability", "difficulty_level": "beginner", "skill_tags": ["Statistics"], "resource_format": "course", "duration_minutes": 480},
    {"title": "STAT 200", "provider": "Penn State", "source_url": "https://online.stat.psu.edu/stat200/", "difficulty_level": "beginner", "skill_tags": ["Statistics"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Data Visualization", "provider": "Kaggle", "source_url": "https://www.kaggle.com/learn/data-visualization", "difficulty_level": "intermediate", "skill_tags": ["Visualization"], "resource_format": "course", "duration_minutes": 180},
    {"title": "Matplotlib Tutorials", "provider": "Matplotlib", "source_url": "https://matplotlib.org/stable/tutorials/index", "difficulty_level": "intermediate", "skill_tags": ["Visualization"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Jupyter Notebook Tutorial", "provider": "freeCodeCamp", "source_url": "https://www.youtube.com/watch?v=HW29067qVWk", "difficulty_level": "beginner", "skill_tags": ["Jupyter"], "resource_format": "video", "duration_minutes": 30},
    {"title": "Jupyter Documentation", "provider": "Project Jupyter", "source_url": "https://jupyter-notebook.readthedocs.io/en/stable/", "difficulty_level": "beginner", "skill_tags": ["Jupyter"], "resource_format": "doc", "duration_minutes": None},

    # QA / Testing
    {"title": "Pytest Tutorial for Beginners", "provider": "freeCodeCamp", "source_url": "https://www.youtube.com/watch?v=cHYq1MRoyI0", "difficulty_level": "beginner", "skill_tags": ["pytest"], "resource_format": "video", "duration_minutes": 85},
    {"title": "pytest Documentation", "provider": "pytest", "source_url": "https://docs.pytest.org/en/stable/getting-started.html", "difficulty_level": "beginner", "skill_tags": ["pytest"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Selenium WebDriver Tutorial", "provider": "SDET-QA", "source_url": "https://www.youtube.com/watch?v=Fr4r6hU8H8A", "difficulty_level": "intermediate", "skill_tags": ["Selenium"], "resource_format": "video", "duration_minutes": 140},
    {"title": "Selenium Documentation", "provider": "Selenium", "source_url": "https://www.selenium.dev/documentation/", "difficulty_level": "intermediate", "skill_tags": ["Selenium"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Postman Beginner's Course", "provider": "Postman", "source_url": "https://www.postman.com/postman/workspace/postman-academy/overview", "difficulty_level": "beginner", "skill_tags": ["Postman"], "resource_format": "course", "duration_minutes": 120},
    {"title": "Postman Getting Started", "provider": "Postman", "source_url": "https://learning.postman.com/docs/getting-started/overview/", "difficulty_level": "beginner", "skill_tags": ["Postman"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Software Testing Tutorial", "provider": "Guru99", "source_url": "https://www.guru99.com/software-testing.html", "difficulty_level": "intermediate", "skill_tags": ["Test Design"], "resource_format": "course", "duration_minutes": 180},
    {"title": "Test Design Techniques", "provider": "ISTQB", "source_url": "https://istqb-glossary.page/test-design-techniques/", "difficulty_level": "intermediate", "skill_tags": ["Test Design"], "resource_format": "article", "duration_minutes": None},

    # IT infrastructure
    {"title": "NDG Linux Unhatched", "provider": "Cisco Networking Academy", "source_url": "https://www.netacad.com/courses/os-it/ndg-linux-unhatched", "difficulty_level": "beginner", "skill_tags": ["Linux"], "resource_format": "course", "duration_minutes": 300},
    {"title": "Linux Journey", "provider": "Linux Journey", "source_url": "https://linuxjourney.com/", "difficulty_level": "beginner", "skill_tags": ["Linux"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Networking Basics", "provider": "Cisco Networking Academy", "source_url": "https://www.netacad.com/courses/networking/networking-basics", "difficulty_level": "beginner", "skill_tags": ["Networking"], "resource_format": "course", "duration_minutes": 240},
    {"title": "What is Networking?", "provider": "Cloudflare", "source_url": "https://www.cloudflare.com/learning/network-layer/what-is-networking/", "difficulty_level": "beginner", "skill_tags": ["Networking"], "resource_format": "article", "duration_minutes": None},

    {"title": "Docker & Kubernetes Full Course", "provider": "freeCodeCamp", "source_url": "https://www.youtube.com/watch?v=Wf2eSG3owoA", "difficulty_level": "advanced", "skill_tags": ["Kubernetes"], "resource_format": "video", "duration_minutes": 360},
    {"title": "Kubernetes Basics", "provider": "Kubernetes", "source_url": "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "difficulty_level": "advanced", "skill_tags": ["Kubernetes"], "resource_format": "doc", "duration_minutes": None},

    {"title": "AWS Cloud Practitioner Essentials", "provider": "AWS", "source_url": "https://www.aws.training/Details/Curriculum?id=20685", "difficulty_level": "beginner", "skill_tags": ["Cloud Basics"], "resource_format": "course", "duration_minutes": 360},
    {"title": "What is Cloud Computing?", "provider": "AWS", "source_url": "https://aws.amazon.com/what-is-cloud-computing/", "difficulty_level": "beginner", "skill_tags": ["Cloud Basics"], "resource_format": "article", "duration_minutes": None},

    # Product
    {"title": "Product Strategy", "provider": "Kellogg", "source_url": "https://www.coursera.org/learn/product-strategy", "difficulty_level": "intermediate", "skill_tags": ["Roadmapping"], "resource_format": "course", "duration_minutes": 300},
    {"title": "Product Roadmaps", "provider": "Atlassian", "source_url": "https://www.atlassian.com/agile/product-management/product-roadmaps", "difficulty_level": "intermediate", "skill_tags": ["Roadmapping"], "resource_format": "article", "duration_minutes": None},

    {"title": "Writing Product Requirements", "provider": "Product School", "source_url": "https://www.youtube.com/@ProductSchoolSanFrancisco", "difficulty_level": "advanced", "skill_tags": ["PRDs"], "resource_format": "video", "duration_minutes": 90},
    {"title": "Requirements Management", "provider": "Atlassian", "source_url": "https://www.atlassian.com/agile/product-management/requirements", "difficulty_level": "advanced", "skill_tags": ["PRDs"], "resource_format": "article", "duration_minutes": None},

    {"title": "Agile with Atlassian Jira", "provider": "Atlassian", "source_url": "https://www.coursera.org/learn/agile-atlassian-jira", "difficulty_level": "intermediate", "skill_tags": ["Agile"], "resource_format": "course", "duration_minutes": 240},
    {"title": "Manifesto for Agile Software Development", "provider": "Agile Alliance", "source_url": "https://agilemanifesto.org/", "difficulty_level": "intermediate", "skill_tags": ["Agile"], "resource_format": "doc", "duration_minutes": None},

    # Design / UX
    {"title": "Figma for Beginners", "provider": "freeCodeCamp", "source_url": "https://www.youtube.com/watch?v=jwCmIBJ8Jtc", "difficulty_level": "beginner", "skill_tags": ["Figma"], "resource_format": "video", "duration_minutes": 90},
    {"title": "Figma Help Center", "provider": "Figma", "source_url": "https://help.figma.com/hc/en-us", "difficulty_level": "beginner", "skill_tags": ["Figma"], "resource_format": "doc", "duration_minutes": None},

    {"title": "Design Systems Course", "provider": "DesignSystems.com", "source_url": "https://www.designsystems.com/", "difficulty_level": "advanced", "skill_tags": ["Design Systems"], "resource_format": "course", "duration_minutes": 180},
    {"title": "Design Systems 101", "provider": "NN/g", "source_url": "https://www.nngroup.com/articles/design-systems-101/", "difficulty_level": "advanced", "skill_tags": ["Design Systems"], "resource_format": "article", "duration_minutes": None},

    {"title": "Web Accessibility Full Course", "provider": "freeCodeCamp", "source_url": "https://www.youtube.com/watch?v=20SHvU2PKsM", "difficulty_level": "intermediate", "skill_tags": ["Accessibility"], "resource_format": "video", "duration_minutes": 210},
    {"title": "Introduction to Web Accessibility", "provider": "W3C WAI", "source_url": "https://www.w3.org/WAI/fundamentals/accessibility-intro/", "difficulty_level": "intermediate", "skill_tags": ["Accessibility"], "resource_format": "doc", "duration_minutes": None},

    {"title": "UX Research and Design", "provider": "Coursera", "source_url": "https://www.coursera.org/learn/ux-research-at-scale-surveys-analytics-online-testing", "difficulty_level": "intermediate", "skill_tags": ["User Research"], "resource_format": "course", "duration_minutes": 240},
    {"title": "When to Use Which User-Experience Research Methods", "provider": "NN/g", "source_url": "https://www.nngroup.com/articles/which-ux-research-methods/", "difficulty_level": "intermediate", "skill_tags": ["User Research"], "resource_format": "article", "duration_minutes": None},
]


async def main() -> None:
    inserted = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        existing_rows = (await session.execute(select(ContentItem.source_url))).scalars().all()
        existing_urls = {_normalize_url(url) for url in existing_rows if url}

        for row in RESOURCES:
            source_url = _normalize_url(str(row["source_url"]))
            if not source_url or source_url in existing_urls:
                skipped += 1
                continue

            item = ContentItem(
                title=str(row["title"]).strip(),
                source_url=source_url,
                difficulty_level=str(row["difficulty_level"]).strip().lower(),
                skill_tags=[str(tag).strip() for tag in row.get("skill_tags", []) if str(tag).strip()],
                provider=str(row["provider"]).strip() or None,
                resource_format=str(row["resource_format"]).strip().lower() or None,
                duration_minutes=row.get("duration_minutes"),
                is_active=True,
            )
            session.add(item)
            existing_urls.add(source_url)
            inserted += 1

        await session.commit()

    print("=" * 72)
    print("Content catalog seeding complete")
    print("=" * 72)
    print(f"Inserted: {inserted}")
    print(f"Skipped:  {skipped}")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
