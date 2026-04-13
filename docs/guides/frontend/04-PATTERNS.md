# Frontend Guide: Patterns

## Формы

### Общие правила

Для базовых form elements использовать:

- `app-input`
- `app-select`
- shared select-компоненты из `frontend/src/components/shared/SearchableSelect.tsx`

Не допускается:

- смешивать на одном экране несколько разных focus/hover contracts без причины
- строить поле через случайные border/background utility-классы, если это уже покрыто foundation layer

### Формы оцениваются по UX-паттерну

Формы нельзя насильно привести к одному layout-паттерну. Они должны оцениваться по типу:

- CRUD form
- compose form
- filter form
- settings form
- dialog action form

Следствие:

- карточки можно нормализовать массово
- формы требуют ручного review по сценарию использования

Для `filter form` дополнительно:

- toolbar и фильтрующий блок лучше держать отдельным feature-компонентом, если page-level файл уже управляет списком, detail modal и compose flow одновременно
- если рядом уже есть удачный плотный list shell, сначала сохранять его внешний контракт и выносить логику/leaf-блоки без агрессивного редизайна

### Dropdown-like UX

Если поле:

- требует поиска
- поддерживает multi-select
- отображает выбранные элементы как chips
- ведёт себя как адресная строка compose-интерфейса

то приоритет у shared select-компонентов, а не у локально стилизованного native `select`.

Причина:

- dropdown affordance должен быть единым по приложению
- локальные стрелки, паддинги и раскрытия быстро создают вторую дизайн-систему
- filter-toolbar с сортировкой и раскрытием фильтров тоже не должен бесконечно разрастаться внутри page-level JSX

### Compose forms

Compose-паттерн должен восприниматься как рабочее пространство, а не как список независимых инпутов.

Особенно это важно для:

- заявлений
- сообщений
- писем
- согласований

Референс по духу:

- `frontend/src/components/requests/RequestComposeModal.tsx`

Базовый контракт:

- адресные строки сверху
- основное содержание формы в центре
- служебные поля ниже и визуально спокойнее
- действия формы собраны в одном предсказуемом footer
- page-level файл держит orchestration, а длинный compose workspace лучше выносить в feature component

## Модалки

### Базовый shell

Для обычных модалок использовать:

- `frontend/src/components/ui/Modal.tsx`

Новый modal pattern нельзя создавать без отдельной причины.

### Геометрия модалок

Target state:

- modal shell: `rounded-2xl`

Текущее переходное состояние:

- mobile может быть компактнее по геометрии, но без отдельного visual contract

### Responsive-логика

Разница между mobile и desktop должна достигаться через:

- responsive spacing
- responsive sizing
- изменение плотности
- sticky header/footer при необходимости

Не должно быть:

- отдельной mobile-версии той же модалки
- дублирования структуры ради платформы

## App Shell

`frontend/src/components/AppShell.tsx` задаёт верхнеуровневый контракт приложения:

- shell background
- header
- global search
- mobile drawers
- навигацию

Следствия:

- feature-страницы не должны переизобретать глобальный shell
- глобальные системные элементы должны оставаться в одном контракте
- capsule-геометрия допустима на уровне shell controls, например у глобального поиска

## Target-pattern registry

| Элемент | Рекомендуемый primitive / радиус | Допустимые исключения | Статус |
| --- | --- | --- | --- |
| Основная секция страницы | `app-surface rounded-2xl` | hero/media pattern по отдельному решению | `ok` |
| Внутренний grouped block | `app-surface-muted rounded-xl` | `rounded-lg`, если блок очень компактный | `needs refactor` |
| Modal shell | `app-surface-elevated rounded-2xl` | переходное mobile state допустимо временно | `ok` |
| Обычный input / textarea / select | `app-input` / `app-select` + `rounded-lg` | нет | `ok` |
| Searchable dropdown trigger | shared `SearchableSelect*` + `rounded-lg` | compose inline-row может быть крупнее по shell | `ok` |
| Compose address row | shared select pattern на базе `app-input` | `rounded-2xl` допустим для compose-shell строки | `ok` |
| Helper / alert / selected block | `app-selected`, `app-feedback-*`, `app-surface-muted` + `rounded-lg`/`rounded-xl` | зависит от веса блока | `needs refactor` |
| Pills / status chips / avatar | `rounded-full` | нет | `ok` |
| `rounded-md` у новых карточек и полей | не использовать | только legacy до отдельной переработки | `legacy` |
| `rounded-[...]` без обоснования | не использовать | только согласованные special cases | `legacy` |

## Do / Don’t

### Делать

- использовать `globals.css` как foundation layer
- опираться на `app-surface`, `app-input`, `app-select`, `app-action-*`
- выбирать радиус из базовой шкалы
- расширять существующий shared primitive, если паттерн уже есть

### Не делать

- не вводить новый радиус “под один экран”
- не стилизовать native `select` локальными хаками, если нужен shared dropdown pattern
- не смешивать old-gray-contract и `app-*` contract в одном новом блоке
- не дублировать shared interaction pattern в page-level JSX
