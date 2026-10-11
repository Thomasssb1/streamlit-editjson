from pathlib import Path

import setuptools

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setuptools.setup(
    name="streamlit-editjson",
    version="1.1.1",
    author="Thomas Beer",
    author_email="thomas.beer04@outlook.com",
    description="A Streamlit component for viewing and editing JSON",
    url="https://github.com/Thomasssb1/streamlit-editjson",
    project_urls={
        "Issues": "https://github.com/Thomasssb1/streamlit-editjson/issues",
        "Releases": "https://github.com/Thomasssb1/streamlit-editjson/releases",
    },
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    classifiers=[],
    python_requires=">=3.7",
    install_requires=["streamlit>=1.2", "jinja2"],
)
