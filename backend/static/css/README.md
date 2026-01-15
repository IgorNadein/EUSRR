# CSS Architecture Documentation

## 🎯 Overview

**Status:** ✅ SCSS Migration Complete (January 2026)  
**Architecture:** 100% SCSS-based, compiled to CSS

This folder contains **compiled CSS files only**. All source styles are written in SCSS and located in `../scss/`.

## 📁 Directory Structure

```
css/
├── app.css                     ← Compiled from scss/main.scss (95 KB)
├── app.css.map                 ← Source map for debugging
├── bootstrap-custom.css        ← Compiled from scss/bootstrap-custom.scss (301 KB)
├── bootstrap-custom.css.map    ← Source map for debugging
├── components/                 ← Legacy folder (kept for git structure)
│   └── .gitkeep
└── README.md                   ← This file
```

## 🔄 Migration History

### Before (Phase 1-5)
- 28+ individual CSS files
- Duplication across components
- Manual maintenance

### After (Phase 6 - January 2026)
- ✅ **2 compiled CSS files** (app.css + bootstrap-custom.css)
- ✅ **30 SCSS component modules**
- ✅ **Centralized build system**
- ✅ **0% duplication**

## 📦 Compiled Files

## 📦 Compiled Files

### 1. app.css (95 KB compressed)
**Source:** `../scss/main.scss`  
**Contains:** All application styles

**Includes:**
- CSS Custom Properties (variables)
- Layout system (grid, navbar, sidebar, rightbar)
- 30 SCSS components
- Spacing utilities
- Responsive styles

**Build Command:**
```bash
cd ../
npm run build:app
```

### 2. bootstrap-custom.css (301 KB compressed)
**Source:** `../scss/bootstrap-custom.scss`  
**Contains:** Bootstrap 5.3.3 with customizations

**Customizations:**
- 8px grid spacing system
- Custom color palette
- Component overrides
- Typography adjustments

**Build Command:**
```bash
cd ../
npm run build:bootstrap
```

## 🏗️ SCSS Architecture

All source styles are in `../scss/`:

```
scss/
├── main.scss                    ← Entry point for app.css
├── bootstrap-custom.scss        ← Entry point for bootstrap
├── custom-bootstrap.scss        ← Bootstrap customizations
├── abstracts/
│   ├── _variables.scss          ← SCSS variables ($var)
│   ├── _css-variables.scss      ← CSS Custom Properties (--var)
│   ├── _mixins.scss             ← Reusable mixins
│   └── _index.scss              ← Exports all abstracts
├── layout/
│   ├── _base-app.scss           ← Main app grid layout
│   └── _chat-layout.scss        ← Chat-specific layout
└── components/
    ├── _navbar.scss             ← Navigation bar
    ├── _sidebar.scss            ← Left sidebar
    ├── _page-header.scss        ← Page headers
    ├── _buttons.scss            ← Button styles
    ├── _cards.scss              ← Card components
    ├── _modals.scss             ← Modal dialogs
    ├── _notifications.scss      ← Notification center
    ├── _layout-spacing.scss     ← Spacing utilities
    ├── _spacing-utils.scss      ← Utility classes
    ├── _rightbar-calendar.scss  ← Calendar in rightbar
    └── ... (30 total components)
```

## 🔧 Development Workflow

### 1. Edit SCSS files
```bash
# Navigate to static folder
cd backend/static

# Edit any SCSS file in scss/ folder
# Example: scss/components/_buttons.scss
```

### 2. Build CSS
```bash
# Build app.css once
npm run build:app

# Or watch for changes (auto-rebuild)
npm run dev
```

### 3. Check output
```bash
# Verify compilation
ls -lh css/app.css

# Check for errors in terminal
```

## 📝 Template Usage

### In base.html
```django
{% load static %}

<head>
  <!-- Bootstrap custom -->
  <link rel="stylesheet" href="{% static 'css/bootstrap-custom.css' %}">
  
  <!-- Application styles -->
  <link rel="stylesheet" href="{% static 'css/app.css' %}">
</head>
```

**Note:** Do NOT link individual component CSS files - everything is in app.css!

## 🎨 CSS Variables

All CSS Custom Properties are compiled into app.css from `scss/abstracts/_css-variables.scss`:

### Spacing (8px grid)
```css
--space-1: 4px
--space-2: 8px
--space-3: 12px
--space-4: 16px
--space-5: 24px
```

### Layout
```css
--navbar-h: 60px
--sidebar-w: 200px
--rightbar-w: 350px
--layout-gap: 16px
--layout-padding-y: 24px
```

### Components
```css
--card-padding: 16px
--card-radius: 14px
--feed-radius: 18px
```

## 🚀 Quick Reference

### Build Commands
```bash
# Build everything
npm run build:app && npm run build:bootstrap

# Watch mode (development)
npm run dev

# Build app.css only
npm run build:app

# Build bootstrap only
npm run build:bootstrap
```

### File Sizes
- **app.css:** 95 KB compressed
- **bootstrap-custom.css:** 301 KB compressed
- **Total:** 396 KB

### Adding New Component
1. Create `scss/components/_new-component.scss`
2. Add `@import 'components/new-component';` to `scss/main.scss`
3. Run `npm run build:app`

## ⚠️ Important Notes

1. **Never edit CSS files directly** - they are auto-generated
2. **Always edit SCSS files** in `../scss/` folder
3. **Always rebuild** after SCSS changes
4. **Source maps included** for debugging (*.css.map)
5. **Components folder kept** for git structure only

## 📚 Documentation

- **SCSS Quick Reference:** [../../docs/guides/SCSS_QUICK_REFERENCE.md](../../docs/guides/SCSS_QUICK_REFERENCE.md)
- **Migration Complete:** [../../docs/completed/CSS_TO_SCSS_MIGRATION_100_PERCENT_COMPLETE.md](../../docs/completed/CSS_TO_SCSS_MIGRATION_100_PERCENT_COMPLETE.md)
- **Phase 6 Report:** [../../docs/reports/CSS_TO_SCSS_PHASE6_FINAL_CLEANUP.md](../../docs/reports/CSS_TO_SCSS_PHASE6_FINAL_CLEANUP.md)

## 🔍 Troubleshooting

### Styles not applying?
1. Check if CSS files are up to date: `npm run build:app`
2. Clear browser cache (Ctrl+F5)
3. Check browser DevTools for CSS loading errors

### Build errors?
1. Check SCSS syntax in modified files
2. Ensure all imports exist in `main.scss`
3. Check terminal output for specific error

### Variables not working?
1. Ensure you're using `var(--variable-name)` syntax
2. Check that `_css-variables.scss` is imported
3. Verify variable is defined in `scss/abstracts/_css-variables.scss`

## 📊 Statistics

- **SCSS Components:** 30 files
- **Total SCSS Lines:** ~4,768 lines
- **CSS Files:** 2 (compiled)
- **Duplication:** 0%
- **Build Time:** ~2 seconds

---

**Last Updated:** January 15, 2026  
**Migration Status:** ✅ Complete  
**Architecture:** SCSS → Compiled CSS  
**Maintainer:** Development Team
