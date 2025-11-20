# CSS Architecture Documentation

## Overview
This document describes the CSS architecture for the EUSRR application after Phase 6 refactoring (October 2024). The architecture follows DRY (Don't Repeat Yourself) principles with centralized shared classes and component-specific styles.

## Dependency Hierarchy

```
variables.css (base layer - CSS custom properties)
    ↓
common.css (shared classes - buttons, badges, avatars, chips, utilities)
    ↓
├── feed-cards.css (feed system - cards, headers, metadata)
├── ios-components.css (iOS UI - cards, lists, accordions)
├── component-specific.css (document-list, employee-list, etc.)
└── base-app.css (app layout - navbar, sidebar, grid)
```

## Core Files

### 1. variables.css
**Purpose**: Centralized CSS custom properties.

**Key Variables**:
```css
/* Layout */
--navbar-h: 60px;
--sidebar-w: 190px;
--rightbar-w: 350px;

/* Radii Scale */
--radius-xs: 4px;   --radius-sm: 8px;   --radius-md: 10px;
--radius-lg: 14px;  --radius-xl: 18px;  --radius-2xl: 24px;

/* Shadow Hierarchy */
--shadow-xs: /* minimal */
--shadow-sm: /* small elements */
--shadow-md: /* standard cards */
--shadow-lg: /* elevated/hover */
--shadow-xl: /* modals */

/* Component Aliases */
--feed-gap: 0.75rem;
--ios-search-radius: var(--radius-md);
--avatar-xs/sm/md/lg/xl: 28px/36px/44px/64px/96px;
```

---

### 2. common.css ⭐ NEW
**Purpose**: Shared classes to eliminate duplication (245 lines).

**Contents**:
```css
/* Buttons */
.btn-icon              /* 36px icon button */
.btn-icon--primary     /* Primary variant */
.btn-icon--danger      /* Danger variant */
.btn-icon--success     /* Success variant */

/* Badges */
.badge-acked           /* Success acknowledgment */
.badge-status          /* Generic status */
.badge-status--pending/approved/rejected  /* State variants */

/* Avatars */
.avatar                /* Base container */
.avatar-xs/sm/md/lg/xl /* Size variants */

/* Feed Meta */
.feed-author           /* Author name */
.feed-sub              /* Subtitle/timestamp */

/* Chips */
.chip                  /* Base chip */
.chip-remove           /* Removable chip */

/* Utilities */
.text-truncate-2       /* 2-line clamp */
.text-truncate-3       /* 3-line clamp */
.custom-scrollbar      /* Custom scrollbar */
```

**Dependencies**: `variables.css`  
**Used By**: Almost all components

---

### 3. feed-cards.css
**Purpose**: Base feed card system.

**Key Classes**:
```css
.feed-stream    /* Container */
.feed-card      /* Individual card */
.feed-hd        /* Header */
.feed-ava       /* Avatar */
.feed-meta      /* Metadata */
.feed-body      /* Content */
.feed-actions   /* Footer actions */
```

**Dependencies**: `variables.css`, `common.css`

---

## Import Order (Critical!)

### In Templates
```html
<link rel="stylesheet" href="{% static 'css/variables.css' %}">
<link rel="stylesheet" href="{% static 'css/components/common.css' %}">
<link rel="stylesheet" href="{% static 'css/components/feed-cards.css' %}">
<!-- Component-specific CSS -->
```

### In index.css
```css
@import 'variables.css';
@import 'common.css';
@import 'feed-cards.css';
/* Other components */
```

**Why This Order?**
1. `variables.css` - defines all CSS custom properties
2. `common.css` - uses variables, defines shared classes
3. `feed-cards.css` - uses variables + common classes
4. Components - use all of the above

---

## Naming Conventions

### Variables
- **Sizes**: `--component-property` (short forms: `-w`, `-h`, `-gap`)
  - Examples: `--navbar-h`, `--sidebar-w`, `--feed-gap`
- **Radii**: `xs/sm/md/lg/xl/2xl` scale (4px - 24px)
- **Shadows**: `xs/sm/md/lg/xl` hierarchy

### Classes (BEM-like)
```css
.block              /* Component/container */
.block__element     /* Child element (or shorthand like .feed-hd) */
.block--modifier    /* Variant/state */
```

**Examples**:
```css
.btn-icon           /* Block */
.btn-icon--primary  /* Modifier */

.badge-status          /* Block */
.badge-status--pending /* Modifier */
```

### Prefixes
- `.ios-*` - iOS-style components
- `.feed-*` - Feed-related classes
- `.req-*` - Request-specific
- `.doc-*` - Document-specific
- `.dept-*` - Department-specific

---

## Component-Specific Files

Each component file contains ONLY unique styles:

### document-list.css
- `#docList` layout
- `.feed-ico` (28px icon)
- `.doc-actions` positioning

**Dependencies**: `common.css` (`.btn-icon`, `.badge-acked`), `feed-cards.css`

### employee-list.css
- `#empList` layout
- Component-specific overrides

**Dependencies**: `common.css` (`.feed-author`, `.feed-sub`), `feed-cards.css`

### request-list.css
- `#reqList` feed layout
- `.req-drawer` action panel
- `.btn-soft-*` variants

**Dependencies**: `common.css` (`.badge-status`), `feed-cards.css`

---

## Best Practices

### 1. Check common.css First
Before creating a new class, check if it exists in `common.css`.

### 2. Use Variables
```css
/* ✅ GOOD */
border-radius: var(--radius-lg);
box-shadow: var(--shadow-md);

/* ❌ BAD */
border-radius: 14px;
box-shadow: 0 4px 12px rgba(0,0,0,.1);
```

### 3. Override Carefully
```css
/* ✅ GOOD: Override specific property */
#empList .feed-author {
  line-height: 1.3;
}

/* ❌ BAD: Complete redefinition */
#empList .feed-author {
  font-weight: 700; /* duplicates common.css */
}
```

### 4. Document Dependencies
```css
/**
 * new-component.css
 * Description
 * 
 * Dependencies:
 * - variables.css (--navbar-h, --radius-md)
 * - common.css (.btn-icon, .badge-status)
 */
```

---

## Phase 6 Results ✅

### Metrics
- **Files Modified**: 16
- **Files Created**: 1 (`common.css`)
- **Files Deleted**: 1 (`feed-header.css` - duplicate)
- **Lines Removed**: ~200 (duplication eliminated)
- **Lines Added**: 245 (`common.css`)
- **Net Change**: +45 lines (centralized)
- **Duplication Rate**: 40% → 0%

### Eliminated Duplication
- `.btn-icon` × 3 → 1 in `common.css`
- `.badge-status` × 2 → 1 in `common.css`
- `.chip` × 2 → 1 in `common.css`
- `.feed-author/.feed-sub` × 4 → 1 in `common.css`
- Variables × 3 → centralized in `variables.css`

### Benefits
1. ✅ **DRY Compliance**: All shared classes defined once
2. ✅ **Maintainability**: Single source of truth
3. ✅ **Consistency**: Unified naming conventions
4. ✅ **Performance**: Smaller CSS after compression
5. ✅ **Documentation**: Clear dependency hierarchy

---

## File Statistics

```
Total Components: 21 files
Total Lines: ~3,500
Shared Classes: 15 (common.css)
Variables: 50+ (variables.css)
Duplication: 0%
```

---

## Adding New Components

### Checklist
1. ✓ Check `common.css` for existing classes
2. ✓ Use variables from `variables.css`
3. ✓ Follow BEM-like naming
4. ✓ Add dependency comments
5. ✓ Update this README

### Example
```css
/**
 * new-component.css
 * Purpose description
 * 
 * Dependencies:
 * - variables.css (--navbar-h)
 * - common.css (.btn-icon)
 */

#newComponent {
  padding: 1rem;
  border-radius: var(--radius-md);
}
```

---

## Maintenance

### Regular Audits
```bash
# Check for duplication
grep -r "\.btn-icon\s*{" static/css/components/

# Check for hardcoded values
grep -r ": [0-9]" static/css/components/ | grep -v "var("
```

### Performance
- **Total Size**: ~50KB uncompressed
- **Gzip Size**: ~12KB estimated
- **Load Time**: <100ms

---

## Troubleshooting

### Styles Not Applying?
1. Check import order (`variables.css` → `common.css` → components)
2. Verify class names (inspect with DevTools)
3. Check specificity conflicts

### Variables Not Working?
1. Ensure `variables.css` imported first
2. Use correct syntax: `var(--variable-name)`
3. Check browser DevTools for computed values

---

## References

- [Phase 6 Summary](../../PHASE6_SUMMARY.md)
- [CSS Custom Properties (MDN)](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties)
- [BEM Methodology](http://getbem.com/)
- [Bootstrap 5.3 Docs](https://getbootstrap.com/docs/5.3/)

---

**Last Updated**: Phase 6 (October 2024)  
**Status**: ✅ Complete and Stable  
**Maintainer**: Development Team
