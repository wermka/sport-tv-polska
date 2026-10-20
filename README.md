# Sport TV Polska — automatyczna wersja internetowa

## Uruchomienie na GitHub Pages

1. Utwórz **publiczne** repozytorium GitHub, np. `sport-tv-polska`.
2. Prześlij do głównego katalogu repozytorium `index.html`, `update_epg.py` i folder `.github/workflows/update.yml` (zachowaj strukturę katalogów).
3. W **Settings → Pages** wybierz **Deploy from a branch**, branch `main`, folder `/ (root)` i zapisz.
4. W **Settings → Secrets and variables → Actions → New repository secret** dodaj sekret o nazwie `XMLTV_URL`, zawierający pełny adres źródła XMLTV, którego używanie jest dozwolone. Nie umieszczaj prywatnego URL w plikach repozytorium.
5. W **Actions → Aktualizacja programu TV → Run workflow** uruchom pierwszą aktualizację.
6. Sprawdź, czy powstał plik `events.json`. Strona będzie dostępna pod `https://TWOJ_LOGIN.github.io/sport-tv-polska/` (jeśli tak nazwiesz repozytorium).
7. Otwórz adres na tablecie w przeglądarce kioskowej i włącz utrzymywanie ekranu oraz automatyczne otwieranie strony po restarcie.

## Ważne ograniczenia

- Bez skonfigurowanego źródła XMLTV **nie pojawią się rzeczywiste wydarzenia**. W projekcie nie ma jeszcze wybranego, zweryfikowanego dostawcy danych.
- GitHub Actions działa w przybliżeniu co 3 godziny; uruchomienia mogą się opóźniać. Panel odświeża dane co 15 minut, jeśli strona jest otwarta.
- EPG może nie zawierać nazw polskich zawodników lub informacji o transmisji na żywo. Filtr jest ostrożny i może pomijać część wydarzeń.
- Publiczne repozytorium i GitHub Pages oznaczają, że wygenerowany `events.json` będzie publicznie dostępny. Sprawdź licencję dostawcy danych; nie publikuj EPG, jeśli licencja na to nie zezwala.
- Powiadomienie na 15 minut przed wydarzeniem działa **wewnątrz otwartej strony**, nie jako systemowe powiadomienie przy wygaszonym ekranie.
- Przed udostępnieniem tacie zweryfikuj numery kanałów Orange i poprawność programu.
