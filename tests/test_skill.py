from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "lockdock"


def test_skill_index_has_frontmatter_and_links_pages():
    text = (SKILL / "SKILL.md").read_text()
    assert text.startswith("---\nname: lockdock\ndescription: ")
    for page in ("modes.md", "theme.md", "pet.md", "agents.md", "browser.md"):
        assert page in text


def test_written_pages_exist_and_theme_page_is_short():
    assert (SKILL / "modes.md").exists()
    assert len((SKILL / "theme.md").read_text().splitlines()) <= 60
