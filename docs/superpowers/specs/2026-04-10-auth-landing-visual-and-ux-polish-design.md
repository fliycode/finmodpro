# Auth Landing Visual And UX Polish Design

## Goal

Polish the login/register landing page so the left-side brand area feels lighter and more coherent, while improving the right-side authentication form with faster keyboard-first interaction and a more standard password visibility control.

## Problem Statement

The current auth landing already has a strong shell and clear split between brand and form, but several details still work against clarity:

1. The left-side slogan block is visually heavier than the rest of the composition.
2. The logo, product title, and Chinese subtitle are spaced too loosely.
3. The inactive auth tab label is slightly too low-contrast.
4. The username field does not autofocus on load.
5. Password visibility uses text buttons instead of a compact eye icon.
6. The core product sentence does not visually emphasize its three key anchors: `文档`, `问答`, `模型`.

These are polish problems, not architecture problems. The goal is to improve density, readability, and input speed without changing the auth flow or route structure.

## Design Summary

Keep the current two-column auth landing and form-in-place login/register switching. Lighten the left statement treatment, tighten the brand lockup spacing, increase inactive tab contrast, autofocus the username field, switch the password toggle to an eye icon button, and lightly emphasize the key nouns inside the brand statement.

## Approach Options

### Option A: Lighten In Place

Keep the existing composition, but reduce the visual weight of the left slogan surface and improve form details.

Pros:
- Minimal structural risk
- Preserves the current visual identity
- Fast to implement and verify

Cons:
- The overall layout stays the same

### Option B: Remove The Slogan Card Entirely

Remove the left white statement surface and render the slogan directly on the blue background.

Pros:
- More open and airy
- Stronger editorial feel

Cons:
- Bigger visual shift
- Higher risk that the statement loses focus against the decorative background

### Recommendation

Use Option A with a strong bias toward making the statement surface much lighter. This captures the user's feedback without destabilizing the rest of the auth entry composition.

## Scope

### In Scope

- Lighten the left statement block
- Tighten title-group spacing on the left
- Improve inactive tab text contrast
- Autofocus the username field when the panel appears
- Replace text password toggle with an eye icon control
- Highlight `文档` / `问答` / `模型` inside the statement copy

### Out Of Scope

- Changing login/register into separate routes or separate pages
- Adding a real forgot-password flow
- Adding enterprise email verification or multi-step registration
- Changing backend auth contracts

## Interaction Design

### 1. Autofocus

When the auth view loads, the username input should receive focus automatically. When switching between login and register tabs, the username field for the newly active panel should also regain focus after the transition mounts.

This keeps the page keyboard-first and removes the extra click before typing.

### 2. Enter-To-Submit

No new logic is required if the current native form submission already works from the password field. This should be preserved and explicitly not broken by the refactor.

### 3. Password Visibility Toggle

Replace the current `显示 / 隐藏` text button with an eye icon button placed in the same trailing position inside the password field.

Behavior:
- same toggle state as today
- clickable with mouse
- accessible label via `aria-label`
- no extra password mode beyond the current shared boolean behavior

## Visual Design

### Left Brand Column

#### Statement Surface

Keep the statement container but make it much lighter:

- reduce background opacity
- reduce border contrast
- reduce shadow strength
- slightly soften or reduce padding if needed

The result should feel closer to a glass panel than a white card.

#### Brand Lockup Spacing

Tighten the relationship between:

- logo tile
- `FinModPro`
- `基于大模型的金融风控平台`

The subtitle should sit closer to the main title, and the icon should feel vertically aligned with the full title stack rather than floating beside it.

#### Statement Emphasis

Keep the sentence:

`一站式风控平台，连接文档、问答与模型，快速完成从风险识别到报告生成。`

But render the key nouns with a subtle emphasis treatment:

- stronger font weight and/or
- brand-colored highlight

Only highlight `文档` / `问答` / `模型`. Do not over-style the rest of the sentence.

### Right Form Column

#### Tabs

Keep the current capsule switcher, but increase inactive text contrast so `注册` is easier to scan when not selected.

#### Password Toggle

The eye icon should be compact, brand-consistent, and visually quieter than the current text control.

## Implementation Notes

### Component Structure

Primary files:

- `frontend/src/components/AuthLanding.vue`
- `frontend/src/views/auth/AuthView.vue`

Auth flow stays the same. The changes are mostly within `AuthLanding.vue`, with a small focus-management addition likely needed in `AuthView.vue` or the landing component itself.

### Rendering The Highlighted Statement

Avoid injecting raw HTML. Use a small computed or helper-driven split rendering strategy in Vue so the sentence remains declarative and safe.

Expected shape:

- an ordered array of fragments
- highlighted fragments for the three keywords
- normal text fragments for everything else

### Focus Management

Use a template ref on the username input and focus it after mount and after auth-tab switches complete. The implementation should tolerate transition timing rather than assuming the element exists synchronously.

## Accessibility

- Password toggle must have an `aria-label`
- Autofocus should target only the active username field
- Highlighted statement words must remain plain readable text, not image content
- Tab button contrast should remain readable in both active and inactive states

## Testing Strategy

Add test-first coverage for any extracted auth helper logic if needed. If focus management is implemented directly in the component without a pure helper, rely on existing frontend test coverage plus build verification.

Required verification:

- `cd frontend && npm test`
- `cd frontend && npm run build`

## Acceptance Criteria

The polish pass is complete when:

1. The left slogan block feels visibly lighter than before and no longer reads as a heavy white slab.
2. The logo/title/subtitle lockup has tighter spacing.
3. Inactive `登录 / 注册` tab text is easier to read.
4. The username field autofocuses on load and after switching tabs.
5. The password visibility control uses an eye icon instead of text.
6. The words `文档` / `问答` / `模型` are visually emphasized inside the brand statement.
7. Existing login and register flow behavior remains unchanged.
