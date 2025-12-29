## Basic Setup

### Formatter Setup

- go download **Ruff** for your python formatter, and also the extension **Svelte for VS Code**
- Set the following in your user Setting for your VScode

```json
// settings.json
{
  "[python]": {
    "editor.tabSize": "2",
    "editor.defaultFormatter": "charliermarsh.ruff"
  },
  "[svelte]": {
    "editor.tabSize": 2,
    "editor.defaultFormatter": "svelte.svelte-vscode"
  }
  // your other settings ...
}
```

- Use tab size 2 for the entire project development
- format document when you need.
- For other IDE/text editor, please consult the documentation for the IDE/text editor

## Reusable Components

## External Library

- ### Others

  - Caching [Valkey](https://valkey.io/)

- ### Frontend

  - localization [svelte-i18n](https://github.com/kaisermann/svelte-i18n/blob/main/docs/Getting%20Started.md)
  - UI component library [svelte-shadcn](https://shadcn-svelte.com/)
  - alert notification [Svelte Sonner](https://svelte-sonner.vercel.app/)
  - form validation [zod](https://zod.dev/)
  - icons [lucide](https://lucide.dev/icons/loader)
  - CSS wrapper [tailwind](https://tailwindcss.com/)

- ### Backend
  - Sql database [SqlAlchemy](https://docs.sqlalchemy.org/en/20/)
  - Server [fastapi](https://fastapi.tiangolo.com/)
  - encryption [bcybt](https://github.com/pyca/bcrypt)
  - jwt [PyJWT](https://pyjwt.readthedocs.io/en/stable/)
  - Background task [Celery](https://docs.celeryq.dev/en/main/getting-started/introduction.html)
  - Caching [Valkey-py](https://valkey-py.readthedocs.io/en/latest/)

### Rules

#### Python file

Dont:

```py
from package import *
```

Do:
```py
from package import funcA, funcB, ...
from package.subpackage import FuncA, FuncB, ...
```
