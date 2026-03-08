from __future__ import annotations


from terraink_py.data import (
    DEFAULT_LAYOUT_ID,
    DEFAULT_THEME_ID,
    get_layout,
    get_theme,
    load_layouts,
    load_themes,
)


class TestLoadThemes:
    def test_load_themes_returns_dict(self) -> None:
        themes = load_themes()
        assert isinstance(themes, dict)
        assert len(themes) > 0

    def test_load_themes_contains_default(self) -> None:
        themes = load_themes()
        assert DEFAULT_THEME_ID in themes

    def test_load_themes_caching(self) -> None:
        themes1 = load_themes()
        themes2 = load_themes()
        assert themes1 is themes2

    def test_theme_structure(self) -> None:
        themes = load_themes()
        for theme in themes.values():
            assert theme.id
            assert theme.name
            assert theme.ui.bg.startswith("#")
            assert theme.ui.text.startswith("#")
            assert theme.map.land.startswith("#")
            assert theme.map.water.startswith("#")
            assert theme.map.roads.major.startswith("#")


class TestGetTheme:
    def test_get_existing_theme(self) -> None:
        theme = get_theme(DEFAULT_THEME_ID)
        assert theme.id == DEFAULT_THEME_ID

    def test_get_random_theme(self) -> None:
        theme = get_theme("random")
        assert theme.id != "random"  # Should return an actual theme
        assert theme.id in load_themes()

    def test_get_nonexistent_theme_returns_default(self) -> None:
        theme = get_theme("nonexistent_theme_12345")
        assert theme.id == DEFAULT_THEME_ID


class TestLoadLayouts:
    def test_load_layouts_returns_dict(self) -> None:
        layouts = load_layouts()
        assert isinstance(layouts, dict)
        assert len(layouts) > 0

    def test_load_layouts_contains_default(self) -> None:
        layouts = load_layouts()
        assert DEFAULT_LAYOUT_ID in layouts

    def test_load_layouts_caching(self) -> None:
        layouts1 = load_layouts()
        layouts2 = load_layouts()
        assert layouts1 is layouts2

    def test_layout_structure(self) -> None:
        layouts = load_layouts()
        for layout in layouts.values():
            assert layout.id
            assert layout.name
            assert layout.width > 0
            assert layout.height > 0
            assert layout.unit
            assert layout.width_cm > 0
            assert layout.height_cm > 0


class TestGetLayout:
    def test_get_existing_layout(self) -> None:
        layout = get_layout(DEFAULT_LAYOUT_ID)
        assert layout.id == DEFAULT_LAYOUT_ID

    def test_get_nonexistent_layout_returns_default(self) -> None:
        layout = get_layout("nonexistent_layout_12345")
        assert layout.id == DEFAULT_LAYOUT_ID

    def test_common_layouts_exist(self) -> None:
        common_layouts = [
            "print_a4_portrait",
            "print_a4_landscape",
            "print_a3_portrait",
            "print_a3_landscape",
        ]
        layouts = load_layouts()
        for layout_id in common_layouts:
            if layout_id in layouts:
                layout = layouts[layout_id]
                assert layout.width_cm > 0
                assert layout.height_cm > 0
