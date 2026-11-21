# Zasady projektu i Git (OBOWIĄZKOWE)
Po zakończeniu każdego zadania i upewnieniu się, że kod nie ma błędów:
1. Sprawdź status (`git status`). Nigdy nie commituj plików `.env`, baz `*.db`/`*.sqlite`, folderów `node_modules/`, `__pycache__/`, `.venv/`.
2. Pobierz najnowsze zmiany: `git pull --rebase origin HEAD`
3. Dodaj zmiany (`git add .`), zrób commit (`git commit -m "feat: opis zmian"`) i wypchnij na GitHuba (`git push origin HEAD`).
4. Nigdy nie używaj `git push --force`.
