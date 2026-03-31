# Markdown Syntax & Styling

Walltext supports a focused subset of Markdown syntax designed explicitly for crisp, beautiful wallpaper designs.

## Supported Elements
- Headings (`#`, `##`, `###`)
- Paragraphs
- Bold (`**bold**`)
- Italic (`*italic*`)
- Code (` `code` `)
- Blockquotes (`> quote`)
- Lists (`- item`)
- Horizontal Rules (`---`)
- Colors (`[color=#ff0000]red text[/color]`)

## Frontmatter
Markdown files can be customized at the block level using Frontmatter at the beginning of the file.

### Example frontmatter:
```md
---
theme: poster
accent: "#ff7a45"
line_spacing: 1.08
align: center
valign: middle
---

# Title!
This is a paragraph.
```

### Pre-configured Themes
Walltext ships with ready-to-use themes for instantaneous color palettes:
- `terminal`
- `poster`
- `note`

### Overrides
You can manually override any colors defined in themes:
`accent`, `heading_fg`, `quote_fg`, `code_fg`, `rule_fg`, `bullet_fg`, and `line_spacing`.
