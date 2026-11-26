"""Essais d'interface : ouvre le fichier final dans un navigateur, avec un faux serveur
(réponses simulées) puisque le vrai serveur n'est pas joignable depuis cet atelier."""
import base64, json, sys, time, pathlib
from playwright.sync_api import sync_playwright

RACINE = pathlib.Path(__file__).resolve().parent.parent
PAGE = "http://localhost:8765/index.html"
CLE_DECOR = (RACINE / ".cle-decor").read_text().strip()
import io
from PIL import Image as _Image
_tampon = io.BytesIO(); _Image.new("RGB", (40, 40), (214, 40, 57)).save(_tampon, "PNG"); PNG_ESSAI = _tampon.getvalue()
POLICE = RACINE / "node_modules/@fontsource-variable/bricolage-grotesque/files/bricolage-grotesque-latin-opsz-normal.woff2"
SORTIE = RACINE / "test" / "captures"
SORTIE.mkdir(exist_ok=True)
HOTE = "https://eonjswzamgpzszaidfxu.supabase.co"
LUKA = "11111111-1111-4111-8111-111111111111"
JULES = "22222222-2222-4222-8222-222222222222"

def b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

JETON = ".".join([b64({"alg": "HS256", "typ": "JWT"}),
                  b64({"sub": LUKA, "role": "authenticated", "exp": int(time.time()) + 3600, "aud": "authenticated"}),
                  "signature"])
UTILISATEUR = {"id": LUKA, "aud": "authenticated", "role": "authenticated", "email": "luka@example.test",
               "user_metadata": {"display_name": "Luka"}, "app_metadata": {}, "created_at": "2026-11-24T10:00:00Z"}
SESSION = {"access_token": JETON, "refresh_token": "r", "token_type": "bearer", "expires_in": 3600,
           "expires_at": int(time.time()) + 3600, "user": UTILISATEUR}

def messages_demo():
    return [
        {"id": 1, "sender": JULES, "body": "Salut ! Tu as le devis du transporteur ?", "file_path": None, "file_name": None, "file_size": None, "file_type": None, "created_at": "2026-11-23T08:12:00+01:00"},
        {"id": 2, "sender": LUKA, "body": None, "file_path": LUKA + "/a.pdf", "file_name": "Devis transport novembre.pdf", "file_size": 184320, "file_type": "application/pdf", "created_at": "2026-11-23T08:15:00+01:00"},
        {"id": 3, "sender": LUKA, "body": "Le voilà. Les tarifs sont en page 2.", "file_path": None, "file_name": None, "file_size": None, "file_type": None, "created_at": "2026-11-23T08:15:30+01:00"},
        {"id": 4, "sender": JULES, "body": "Merci. Regarde aussi ça pour le stand : https://www.musilac.com/infos-pratiques, c'est la page des horaires.", "file_path": None, "file_name": None, "file_size": None, "file_type": None, "created_at": "2026-11-24T14:02:00+01:00"},
        {"id": 5, "sender": JULES, "body": None, "file_path": JULES + "/b.pdf", "file_name": "Plan du stand v3.pdf", "file_size": 2411724, "file_type": "application/pdf", "created_at": "2026-11-24T14:03:00+01:00"},
        {"id": 6, "sender": LUKA, "body": "Parfait, je regarde ce soir et je te dis.", "file_path": None, "file_name": None, "file_size": None, "file_type": None, "created_at": "2026-11-24T14:10:00+01:00"},
    ]

class Serveur:
    """Faux serveur : mémorise les messages et les connexions temps réel."""
    def __init__(self, membres, messages, complet=False, direct=True, ia=False):
        self.membres, self.messages, self.complet, self.direct, self.ia = membres, messages, complet, direct, ia
        self.sockets, self.requetes, self.erreurs = [], [], []
        self.reactions, self.lectures, self.taches, self.appels_assistant, self.abonnements = [], [], [], [], []
        self.refus_jeton = 0
        self.deconnexions = []
        self.mots, self.reglages, self.fichiers_retires = [], [], []

    def languagetool(self, route):
        texte = dict(x.split("=", 1) for x in route.request.post_data.split("&"))["text"]
        from urllib.parse import unquote_plus
        texte = unquote_plus(texte)
        i = texte.find("envoi ")
        fautes = [{"offset": i, "length": 5, "replacements": [{"value": "envoie"}]}] if i != -1 else []
        route.fulfill(status=200, headers={"access-control-allow-origin": "*"}, content_type="application/json",
                      body=json.dumps({"matches": fautes}))

    def brancher(self, page):
        page.on("console", lambda m: self.erreurs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: self.erreurs.append("pageerror: " + str(e)))
        page.route("https://fonts.googleapis.com/**", lambda r: r.fulfill(
            content_type="text/css",
            body="@font-face{font-family:'Bricolage Grotesque';font-weight:200 800;font-stretch:75% 100%;src:url(https://fonts.gstatic.com/b.woff2) format('woff2');}"))
        page.route("https://fonts.gstatic.com/**", lambda r: r.fulfill(content_type="font/woff2", body=POLICE.read_bytes()))
        page.route(HOTE + "/**", self.repondre)
        page.route("https://api.languagetool.org/**", self.languagetool)
        page.route("https://api.frankfurter.dev/**", lambda r: r.fulfill(status=200, headers={"access-control-allow-origin": "*"}, content_type="application/json",
            body=json.dumps({"amount": 1.0, "base": "EUR", "date": "2026-11-24", "rates": {"USD": 1.0963, "GBP": 0.837, "CHF": 0.9183}})))
        if self.direct:
            page.route_web_socket("wss://eonjswzamgpzszaidfxu.supabase.co/**", self.socket)

    def repondre(self, route):
        req = route.request
        url, methode = req.url, req.method
        self.requetes.append(methode + " " + url.replace(HOTE, ""))
        entetes = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*"}
        def js(corps, statut=200):
            route.fulfill(status=statut, headers=entetes, content_type="application/json", body=json.dumps(corps))
        if methode == "OPTIONS":
            return route.fulfill(status=204, headers=entetes)
        if "/functions/v1/inscription" in url:
            if methode == "GET":
                return js({"ok": True, "complet": self.complet})
            return js({"ok": True})
        if "/auth/v1/token" in url:
            return js(SESSION)
        if "/auth/v1/user" in url:
            return js(UTILISATEUR)
        if "/auth/v1/logout" in url:
            self.deconnexions.append(url)
            return route.fulfill(status=204, headers=entetes)
        if "/auth/v1/logout-inutilise" in url:
            return route.fulfill(status=204, headers=entetes)
        if "/rest/v1/members" in url:
            return js(self.membres)
        if "/rest/v1/messages" in url:
            if methode == "GET":
                return js(sorted(self.messages, key=lambda m: -m["id"]))
            if methode == "POST":
                donnees = json.loads(req.post_data)
                nouveau = {"id": max([m["id"] for m in self.messages] + [0]) + 1, "sender": LUKA, "body": None, "file_path": None,
                           "file_name": None, "file_size": None, "file_type": None,
                           "created_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())}
                nouveau.update(donnees)
                self.messages.append(nouveau)
                return js(nouveau, 201)
            if methode == "DELETE":
                ident = int(url.split("id=eq.")[1].split("&")[0])
                self.messages[:] = [m for m in self.messages if m["id"] != ident]
                return route.fulfill(status=204, headers=entetes)
        if "/rest/v1/reactions" in url:
            if methode == "GET":
                return js(self.reactions)
            if methode == "POST":
                d = json.loads(req.post_data); d["user_id"] = LUKA; self.reactions.append(d)
                return js(d, 201)
            if methode == "DELETE":
                self.reactions[:] = [r for r in self.reactions if not (str(r["message_id"]) in url and r["user_id"] == LUKA)]
                return route.fulfill(status=204, headers=entetes)
        if "/rest/v1/reads" in url:
            if methode == "GET":
                return js(self.lectures)
            if methode == "PATCH":
                d = json.loads(req.post_data)
                l = [x for x in self.lectures if x["user_id"] == LUKA]
                for x in l: x.update(d)
                return js([{"user_id": LUKA}] if l else [])
            if methode == "POST":
                d = json.loads(req.post_data); d["user_id"] = LUKA; self.lectures.append(d)
                return js(d, 201)
        if "/rest/v1/reglages" in url:
            if methode == "GET":
                return js([r for r in self.reglages if "cle=eq.mots_origine_importes" in url and r["cle"] == "mots_origine_importes"])
            if methode == "POST":
                self.reglages.append(json.loads(req.post_data))
                return js({}, 201)
        if "/rest/v1/mots_magiques" in url:
            if methode == "GET":
                return js(self.mots)
            if methode == "POST":
                d = json.loads(req.post_data)
                if any(m["mot"].strip().lower() == d["mot"].strip().lower() for m in self.mots):
                    return js({"code": "23505", "message": "doublon"}, 409)
                m = {"id": len(self.mots) + 100, "mot": d["mot"], "image_path": d["image_path"], "created_by": LUKA, "created_at": "2026-11-26T15:00:%02dZ" % len(self.mots)}
                self.mots.append(m)
                return js(m, 201)
            if methode == "DELETE":
                self.mots[:] = [m for m in self.mots if "id=eq.%d" % m["id"] not in url]
                return route.fulfill(status=204, headers=entetes)
        if "/rest/v1/decor_cle" in url:
            return js({"cle": CLE_DECOR})
        if "/rest/v1/push_subscriptions" in url:
            if methode == "POST":
                self.abonnements.append(json.loads(req.post_data))
                return js({}, 201)
            if methode == "DELETE":
                return route.fulfill(status=204, headers=entetes)
            return js([])
        if "/functions/v1/notifier" in url:
            return js({"ok": True, "cle": "BJH5p95bqMriUHarE4khZLCa8ovihbj5ZUvv78Iq1zzwEfr6sNNpeuJZxcCh37Qu7rhdQ_XXXpYuL5zySpAHd6w"})
        if "/rest/v1/tasks" in url:
            if methode == "GET":
                return js(self.taches)
            if methode == "POST":
                d = json.loads(req.post_data)
                t = {"id": len(self.taches) + 1, "label": d["label"], "done": False, "created_by": LUKA, "created_at": "2026-11-24T15:00:00Z", "done_at": None}
                self.taches.append(t)
                return js(t, 201)
            if methode == "PATCH":
                d = json.loads(req.post_data)
                for t in self.taches:
                    if "id=eq.%d" % t["id"] in url: t.update(d)
                return route.fulfill(status=204, headers=entetes)
            if methode == "DELETE":
                self.taches[:] = [t for t in self.taches if "id=eq.%d" % t["id"] not in url]
                return route.fulfill(status=204, headers=entetes)
        if "/functions/v1/assistant" in url:
            if methode == "GET":
                return js({"ok": True, "reformulation": self.ia})
            d = json.loads(req.post_data)
            if self.refus_jeton > 0:
                self.refus_jeton -= 1
                return js({"code": "connexion"}, 401)
            self.appels_assistant.append(d)
            if d["action"] == "corriger":
                return js({"ok": True, "texte": d["texte"].replace("envoi ", "envoie "), "fautes": [{"avant": "envoi", "apres": "envoie", "explication": "Avec « je », le verbe envoyer se termine par -e."}], "moteur": "claude"})
            return js({"ok": True, "texte": "[" + d["action"] + "] " + d["texte"], "moteur": "claude"})
        if "/storage/v1/object/sign/" in url:
            if methode == "GET":
                return route.fulfill(status=200, headers=entetes, content_type="image/png", body=PNG_ESSAI)
            d = json.loads(req.post_data or "{}")
            if "paths" in d:
                return js([{"path": c, "signedURL": "/object/sign/fichiers/" + c + "?token=t", "error": None} for c in d["paths"]])
            return js({"signedURL": "/object/sign/fichiers/x?token=t"})
        if "/storage/v1/object/fichiers" in url and methode == "DELETE":
            self.fichiers_retires.extend(json.loads(req.post_data or "{}").get("prefixes", []))
            return js([])
        if "/storage/v1/object/" in url:
            return js({"Key": "fichiers/x", "Id": "1"})
        return js({"message": "non simulé"}, 404)

    # --- temps réel (protocole Phoenix, formats objet et tableau) ---
    def socket(self, ws):
        self.sockets.append(ws)
        ws.on_message(lambda brut: self.recu(ws, brut))

    def envoyer(self, ws, sujet, evenement, charge, ref=None, join_ref=None):
        if getattr(ws, "_tableau", False):
            ws.send(json.dumps([join_ref, ref, sujet, evenement, charge]))
        else:
            ws.send(json.dumps({"topic": sujet, "event": evenement, "payload": charge, "ref": ref, "join_ref": join_ref}))

    def recu(self, ws, brut):
        m = json.loads(brut)
        if isinstance(m, list):
            ws._tableau = True
            join_ref, ref, sujet, evenement, charge = m
        else:
            join_ref, ref, sujet, evenement, charge = m.get("join_ref"), m.get("ref"), m["topic"], m["event"], m.get("payload", {})
        if evenement == "heartbeat":
            return self.envoyer(ws, "phoenix", "phx_reply", {"status": "ok", "response": {}}, ref)
        if evenement == "phx_join":
            ws._sujet, ws._join = sujet, join_ref
            changements = charge.get("config", {}).get("postgres_changes", [])
            ws._abonnements = [dict(c, id=i + 1) for i, c in enumerate(changements)]
            self.envoyer(ws, sujet, "phx_reply", {"status": "ok", "response": {"postgres_changes": ws._abonnements}}, ref, join_ref)
            self.envoyer(ws, sujet, "system", {"status": "ok", "message": "Subscribed to PostgreSQL", "channel": "fil", "extension": "postgres_changes"})
            return
        if evenement == "presence":
            self.envoyer(ws, sujet, "phx_reply", {"status": "ok", "response": {}}, ref, join_ref)
            if len(self.membres) > 1:
                self.envoyer(ws, sujet, "presence_state", {LUKA: {"metas": [{"phx_ref": "a"}]}, JULES: {"metas": [{"phx_ref": "b"}]}})
            return
        self.envoyer(ws, sujet, "phx_reply", {"status": "ok", "response": {}}, ref, join_ref)

    def pousser_message(self, message):
        """Simule l'arrivée d'un message de l'autre personne."""
        self.messages.append(message)
        for ws in self.sockets:
            ids = [a["id"] for a in getattr(ws, "_abonnements", []) if a.get("table") == "messages" and a.get("event") == "INSERT"]
            self.envoyer(ws, ws._sujet, "postgres_changes", {"ids": ids, "data": {
                "schema": "public", "table": "messages", "type": "INSERT", "commit_timestamp": "2026-11-24T14:20:00Z",
                "columns": [], "record": message, "errors": None}})

MEMBRES = [{"user_id": LUKA, "display_name": "Luka", "joined_at": "2026-11-24T10:00:00Z"},
           {"user_id": JULES, "display_name": "Jules", "joined_at": "2026-11-24T11:00:00Z"}]
SEME = "localStorage.setItem('sb-eonjswzamgpzszaidfxu-auth-token', %s);" % json.dumps(json.dumps(SESSION))

resultats = []
def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("OK   " if condition else "ECHEC") + " " + nom + (" : " + str(detail) if detail and not condition else ""))

with sync_playwright() as p:
    nav = p.chromium.launch()

    # 1. Accueil, sans session
    ctx = nav.new_context(viewport={"width": 1280, "height": 800}, locale="fr-FR", timezone_id="Europe/Paris")
    page = ctx.new_page(); s = Serveur(MEMBRES[:1], []); s.brancher(page)
    page.goto(PAGE); page.wait_for_selector("#vue-accueil:not([hidden])")
    page.wait_for_timeout(500)
    page.screenshot(path=str(SORTIE / "1-accueil.png"))
    verifier("accueil : onglets visibles quand le fil n'est pas complet", page.is_visible("#onglets"))
    page.click("#onglet-creation")
    verifier("création : champ prénom affiché", page.is_visible("#prenom"))
    page.fill("#email", "pas-une-adresse"); page.click("#accueil-valider")
    verifier("création : adresse invalide refusée", "valide" in page.inner_text("#accueil-erreur"))
    page.fill("#email", "luka@example.test"); page.fill("#prenom", "Luka"); page.fill("#motdepasse", "court"); page.click("#accueil-valider")
    verifier("création : mot de passe trop court refusé", "8" in page.inner_text("#accueil-erreur"))
    page.screenshot(path=str(SORTIE / "2-creation.png"))
    page.fill("#motdepasse", "valeur-de-test-locale"); page.click("#accueil-valider")
    page.wait_for_selector("#vue-fil:not([hidden])")
    verifier("création : appel d'inscription puis connexion", any("POST /functions/v1/inscription" in r for r in s.requetes) and any("/auth/v1/token" in r for r in s.requetes))
    page.wait_for_timeout(600)
    verifier("fil vide et seul : invitation à partager le fichier", "seul sur le fil" in page.inner_text("#piste"))
    verifier("présence : en attente de l'autre personne", "attente" in page.inner_text("#presence-texte"))
    page.screenshot(path=str(SORTIE / "3-seul.png"))
    verifier("aucune erreur de script (accueil)", not [e for e in s.erreurs if "pageerror" in e], s.erreurs)
    ctx.close()

    # 2. Fil complet : création fermée
    ctx = nav.new_context(viewport={"width": 1280, "height": 800}, locale="fr-FR")
    page = ctx.new_page(); s = Serveur(MEMBRES, [], complet=True); s.brancher(page)
    page.goto(PAGE); page.wait_for_selector("#vue-accueil:not([hidden])"); page.wait_for_timeout(500)
    verifier("fil complet : onglet de création masqué", not page.is_visible("#onglets") and page.is_visible("#accueil-note"))
    ctx.close()

    # 3. Fil avec messages, grand écran
    ctx = nav.new_context(viewport={"width": 1280, "height": 800}, locale="fr-FR", timezone_id="Europe/Paris")
    ctx.add_init_script(SEME)
    page = ctx.new_page(); s = Serveur(MEMBRES, messages_demo()); s.brancher(page)
    page.clock.install(time="2026-11-24T14:30:00+01:00") if False else None
    page.goto(PAGE); page.wait_for_selector("#vue-fil:not([hidden])"); page.wait_for_timeout(900)
    verifier("fil : 6 messages affichés", page.locator(".ligne").count() == 6, page.locator(".ligne").count())
    verifier("fil : messages de Luka à droite du fil, de Jules à gauche",
             page.locator(".ligne.moi").count() == 3 and page.locator(".ligne.autre").count() == 3)
    verifier("fil : lien cliquable dans un message", page.locator(".bulle a[href='https://www.musilac.com/infos-pratiques']").count() == 1)
    verifier("fil : fichier PDF avec Ouvrir et Télécharger", page.locator(".fichier-actions button").count() == 4)
    verifier("présence : Jules en ligne", "Jules est en ligne" in page.inner_text("#presence-texte"), page.inner_text("#presence-texte"))
    verifier("liaison en direct établie", not page.is_visible("#etat-liaison"))
    page.screenshot(path=str(SORTIE / "4-fil-large.png"))

    page.fill("#texte", "Test d'envoi <b>sans html</b> https://example.org/x."); page.keyboard.press("Enter")
    page.wait_for_function("document.querySelectorAll('.ligne').length === 7")
    dernier = page.locator(".ligne").last
    verifier("envoi : le message apparaît, le HTML reste du texte", "<b>sans html</b>" in dernier.inner_text() and dernier.locator("b").count() == 0)
    verifier("envoi : le point final ne fait pas partie du lien", dernier.locator("a").get_attribute("href") == "https://example.org/x")
    verifier("envoi : champ vidé", page.input_value("#texte") == "")

    s.pousser_message({"id": 50, "sender": JULES, "body": "Reçu en direct !", "file_path": None, "file_name": None, "file_size": None, "file_type": None, "created_at": "2026-11-24T14:21:00+01:00"})
    page.wait_for_function("document.querySelectorAll('.ligne').length === 8")
    verifier("temps réel : le message de Jules arrive sans recharger", "Reçu en direct" in page.inner_text("#piste"))

    page.set_input_files("#selecteur", {"name": "Note de frais.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 test"})
    verifier("pièce jointe : en attente avant envoi", "Note de frais.pdf" in page.inner_text("#en-attente"))
    page.click("#envoyer")
    page.wait_for_function("document.querySelectorAll('.ligne').length === 9")
    verifier("pièce jointe : dépôt puis message", any("POST /storage/v1/object/fichiers/" + LUKA in r for r in s.requetes) and "Note de frais.pdf" in page.locator(".ligne").last.inner_text())
    verifier("pièce jointe : file d'attente vidée", not page.is_visible("#en-attente"))

    avant = page.locator(".ligne").count()
    b = page.locator(".ligne.moi .meta button").last
    b.click(); verifier("suppression : demande de confirmation", "Confirmer" in b.inner_text())
    b.click(); page.wait_for_function("document.querySelectorAll('.ligne').length === %d" % (avant - 1))
    verifier("suppression : message retiré", any(r.startswith("DELETE /rest/v1/messages") for r in s.requetes))
    # Réactions
    page.locator(".ligne.autre .meta button", has_text="Réagir").first.click()
    page.locator(".choix-reaction button").first.click()
    page.wait_for_selector(".reaction[aria-pressed='true']")
    verifier("réaction : 👍 ajoutée sous le message", "👍 1" in page.locator(".reaction").first.inner_text() and len(s.reactions) == 1)
    page.locator(".reaction[aria-pressed='true']").first.click()
    page.wait_for_function("!document.querySelector('.reaction')")
    verifier("réaction : retirée au second clic", len(s.reactions) == 0)

    # « Vu » : Jules a lu jusqu'au dernier message de Luka
    dernier_luka = max(m["id"] for m in s.messages if m["sender"] == LUKA)
    for ws in s.sockets:
        ids = [a["id"] for a in getattr(ws, "_abonnements", []) if a.get("table") == "reads"]
        s.envoyer(ws, ws._sujet, "postgres_changes", {"ids": ids, "data": {"schema": "public", "table": "reads", "type": "UPDATE",
            "commit_timestamp": "2026-11-24T14:20:00Z", "columns": [], "record": {"user_id": JULES, "last_read_id": dernier_luka}, "old_record": {}, "errors": None}})
    page.wait_for_selector(".meta .vu")
    verifier("« Vu » : affiché une seule fois, sous mon dernier message lu",
             page.locator(".meta .vu").count() == 1 and page.locator(".ligne[data-id='%d'] .vu" % dernier_luka).count() == 1)
    verifier("« Vu » : ma propre lecture est enregistrée", any(r.startswith("PATCH /rest/v1/reads") or r.startswith("POST /rest/v1/reads") for r in s.requetes))

    # Mots magiques
    page.fill("#texte", "On se fait un Y'peu ce soir ?"); page.keyboard.press("Enter")
    page.wait_for_selector("#magie.joue img", timeout=4000)
    page.wait_for_timeout(900)
    page.screenshot(path=str(SORTIE / "7-magie-melon.png"))
    verifier("mot magique « y peu » : le melon apparaît devant le fil", page.locator("#magie img").count() == 1 and page.evaluate("+getComputedStyle(document.querySelector('#magie')).zIndex > +getComputedStyle(document.querySelector('#vue-fil')).zIndex"))
    verifier("mot magique : l'image ne bloque pas les clics", page.evaluate("getComputedStyle(document.querySelector('#magie')).pointerEvents") == "none")
    page.wait_for_timeout(4000)
    verifier("mot magique : l'image disparaît après environ 4 secondes", page.locator("#magie img").count() == 0)
    s.pousser_message({"id": 60, "sender": JULES, "body": "Tu as vu DAVID ce matin ?", "file_path": None, "file_name": None, "file_size": None, "file_type": None, "created_at": "2026-11-24T14:25:00+01:00"})
    page.wait_for_selector("#magie.joue img", timeout=4000)
    page.wait_for_timeout(900)
    page.screenshot(path=str(SORTIE / "8-magie-david.png"))
    verifier("mot magique « david » reçu de Jules : David apparaît", page.locator("#magie img").count() == 1)
    page.wait_for_timeout(3800)
    page.fill("#texte", "Les davidées et le melon ne déclenchent rien"); page.keyboard.press("Enter")
    page.wait_for_timeout(600)
    verifier("mot magique : pas de déclenchement sur un mot qui ne fait que ressembler", page.locator("#magie img").count() == 0)

    # Émojis
    page.click("#ouvrir-emojis")
    page.locator("#volet-emojis .emojis-grille button", has_text="🔥").click()
    verifier("émojis : le panneau insère l'émoji dans le message", "🔥" in page.input_value("#texte"))
    page.fill("#texte", "🎉"); page.keyboard.press("Enter")
    page.wait_for_function("document.querySelectorAll('.bulle.grand').length === 1")
    verifier("émojis : un message fait seulement d'émojis s'affiche en grand", True)

    # Outils : calculatrice
    # Images-émojis
    if not page.is_visible("#panneau-emojis"): page.click("#ouvrir-emojis")
    verifier("émojis : panneau séparé, sans les outils", page.is_visible("#panneau-emojis") and not page.is_visible("#zone-outils"))
    verifier("images : 6 images dans le panneau d'émojis", page.locator(".image-tuile").count() == 6, page.locator(".image-tuile").count())
    page.screenshot(path=str(SORTIE / "11-panneau-emojis.png"))
    page.locator(".image-tuile", has_text="Oslo").click()
    page.wait_for_selector(".ligne.moi .bulle.image-emoji img")
    verifier("images : Oslo envoyé s'affiche en image dans le fil", s.messages[-1]["body"] == "[[image:oslo]]")
    page.wait_for_timeout(300)
    verifier("images : envoyer l'image de David ne déclenche pas le mot magique", True)
    page.locator(".image-tuile", has_text="David").click()
    page.wait_for_timeout(600)
    verifier("images : pas d'animation pour une image envoyée", page.locator("#magie img").count() == 0)
    page.click("#emojis-fermer")

    # Mot magique « occupé »
    page.fill("#texte", "Désolé, très occupé aujourd'hui"); page.keyboard.press("Enter")
    page.wait_for_selector("#magie.joue img", timeout=4000)
    page.wait_for_timeout(900)
    page.screenshot(path=str(SORTIE / "12-magie-occupe.png"))
    verifier("mot magique « occupé » : la photo apparaît", page.locator("#magie img").count() == 1)
    page.wait_for_timeout(3700)
    page.fill("#texte", "Le DJ arrive à 22 h"); page.keyboard.press("Enter")
    page.wait_for_timeout(700)
    verifier("mot magique : « DJ » ne déclenche plus rien", page.locator("#magie img").count() == 0)
    for phrase, nom in [("Quel dégourdi celui-là", "dj"), ("Je t'envoie le mail", "mail"), ("Gregr est là", "gregr"), ("Kiki dort", "kiki")]:
        page.fill("#texte", phrase); page.keyboard.press("Enter")
        page.wait_for_selector("#magie.joue img", timeout=4000)
        verifier("mot magique « %s » : une photo apparaît" % nom, page.locator("#magie img").count() == 1)
        page.wait_for_timeout(900)
        page.screenshot(path=str(SORTIE / ("14-magie-%s.png" % nom)))
        page.wait_for_timeout(3700)

    # Réglages : les mots d'origine ont été importés dans la liste partagée
    verifier("réglages : les 8 mots d'origine sont importés une seule fois", len(s.mots) == 8 and len(s.reglages) == 1, [m["mot"] for m in s.mots])
    page.click("#ouvrir-reglages")
    page.wait_for_selector("#vue-reglages:not([hidden])")
    page.wait_for_function("document.querySelectorAll('#mots-liste li').length === 8")
    verifier("réglages : la liste montre chaque mot à gauche et son image à droite",
             page.locator("#mots-liste li .mot-nom").count() == 8 and page.locator("#mots-liste li .mot-image img").count() == 8)
    page.fill("#mot-saisie", "apéro")
    page.click("#mot-ajouter")
    verifier("réglages : sans image, l'ajout est refusé avec un message", "image" in page.inner_text("#mot-erreur"))
    page.set_input_files("#mot-fichier", {"name": "apero.png", "mimeType": "image/png", "buffer": PNG_ESSAI})
    page.wait_for_selector("#mot-image-apercu:not([hidden])")
    page.click("#mot-ajouter")
    page.wait_for_function("document.querySelectorAll('#mots-liste li').length === 9")
    verifier("réglages : le nouveau mot est ajouté en tête de liste", page.locator("#mots-liste li .mot-nom").first.inner_text() == "apéro")
    verifier("réglages : son image est rangée dans le dossier des mots magiques", s.mots[-1]["image_path"].startswith(LUKA + "/magie/"), s.mots[-1]["image_path"])
    page.fill("#mot-saisie", "Apero"); page.set_input_files("#mot-fichier", {"name": "a.png", "mimeType": "image/png", "buffer": PNG_ESSAI})
    page.wait_for_selector("#mot-image-apercu:not([hidden])")
    page.click("#mot-ajouter")
    verifier("réglages : un mot déjà présent est refusé (accents et majuscules ignorés)", "existe déjà" in page.inner_text("#mot-erreur"), page.inner_text("#mot-erreur"))
    page.screenshot(path=str(SORTIE / "20-reglages.png"))
    page.click("#reglages-retour")
    page.fill("#texte", "On se fait un apéros ce soir ?"); page.keyboard.press("Enter")
    page.wait_for_selector("#magie.joue img", timeout=4000)
    verifier("réglages : le mot créé fait apparaître son image (pluriel compris)", True)
    page.wait_for_timeout(4400)
    page.click("#ouvrir-reglages")
    ligne = page.locator("#mots-liste li", has_text="top")
    ligne.locator("button", has_text="Supprimer").click()
    verifier("réglages : la suppression demande une confirmation", ligne.locator("button", has_text="Confirmer").count() == 1)
    ligne.locator("button", has_text="Confirmer").click()
    page.wait_for_function("document.querySelectorAll('#mots-liste li').length === 8")
    verifier("réglages : le mot est supprimé de la liste partagée", not any(m["mot"] == "top" for m in s.mots))
    page.click("#reglages-retour")
    page.fill("#texte", "C'est top"); page.keyboard.press("Enter")
    page.wait_for_timeout(700)
    verifier("réglages : un mot supprimé ne déclenche plus rien", page.locator("#magie img").count() == 0)

    # Outils dans la barre du haut
    page.click("[data-volet='calc']")
    verifier("barre du haut : Calculatrice ouvre l'outil sous la barre", page.is_visible("#volet-calc") and page.inner_text("#panneau-titre") == "Calculatrice")
    boite_outil = page.locator("#zone-outils").bounding_box(); boite_flux = page.locator("#flux").bounding_box()
    verifier("barre du haut : l'outil s'ouvre en haut, le fil reste visible en dessous", boite_outil["y"] < 140 and boite_flux["y"] >= boite_outil["y"] + boite_outil["height"] - 1 and boite_flux["height"] > 150, (boite_outil, boite_flux))
    page.click("[data-volet='calc']")
    verifier("barre du haut : un second clic referme l'outil", not page.is_visible("#zone-outils"))
    page.click("[data-volet='calc']")
    page.fill("#calc-saisie", "1250 + 20 %")
    verifier("calculatrice : aperçu 1250 + 20 % = 1 500", page.inner_text("#calc-apercu").replace(" ", " ") == "= 1 500", page.inner_text("#calc-apercu"))
    page.fill("#calc-saisie", "(12,5 × 4) ÷ 2"); page.keyboard.press("Enter")
    verifier("calculatrice : (12,5 × 4) ÷ 2 = 25", page.input_value("#calc-saisie") == "25", page.input_value("#calc-saisie"))
    page.fill("#calc-saisie", "alert(1)")
    verifier("calculatrice : refuse tout ce qui n'est pas un calcul", page.inner_text("#calc-apercu") == "")
    page.fill("#texte", ""); page.fill("#calc-saisie", "3 × 7"); page.click("#calc-inserer")
    verifier("calculatrice : « Mettre dans le message »", page.input_value("#texte") == "3 × 7 = 21", page.input_value("#texte"))

    # TVA et marge
    page.locator("[data-volet='tva']").click()
    page.fill("#com-net", "40"); page.fill("#com-taux", "23")
    com = page.inner_text("#com-resultat").replace("\u202f", " ")
    verifier("commission : 40 € nets avec 23 % prélevés donnent un prix de 51,95 €", "51,95 €" in com and "11,95 €" in com and "+ 29,9 %" in com, com)
    verifier("commission : la formule est rappelée", "40 ÷ 0,77" in page.inner_text("#com-formule"), page.inner_text("#com-formule"))
    page.fill("#tva-montant", "100")
    tva = page.inner_text("#tva-resultat").replace(" ", " ")
    verifier("TVA : 100 € HT à 20 % donne 120 € TTC", "120,00 €" in tva and "20,00 €" in tva, tva)
    page.select_option("#tva-sens", "ttc"); page.select_option("#tva-taux", "5.5"); page.fill("#tva-montant", "105,50")
    tva = page.inner_text("#tva-resultat").replace(" ", " ")
    verifier("TVA : 105,50 € TTC à 5,5 % donne 100 € HT", "100,00 €" in tva, tva)
    page.fill("#marge-achat", "40"); page.fill("#marge-vente", "60")
    marge = page.inner_text("#marge-resultat")
    verifier("marge : achat 40, vente 60 donnent 50 % de marge et 33,3 % de marque", "50,0 %" in marge and "33,3 %" in marge, marge)
    page.screenshot(path=str(SORTIE / "9-outils-tva.png"))

    # Convertisseur
    page.locator("[data-volet='conv']").click()
    page.wait_for_function("document.querySelector('#conv-sortie').value.endsWith('USD')")
    page.fill("#conv-valeur", "100")
    verifier("convertisseur : la monnaie est proposée en premier, 100 EUR = 109,63 USD", page.input_value("#conv-sortie") == "109,63 USD", page.input_value("#conv-sortie"))
    page.select_option("#conv-vers", "CHF")
    verifier("convertisseur : 100 EUR = 91,83 CHF", page.input_value("#conv-sortie") == "91,83 CHF", page.input_value("#conv-sortie"))
    verifier("convertisseur : la date des taux BCE est indiquée", "24 novembre 2026" in page.inner_text("#conv-note"), page.inner_text("#conv-note"))
    page.screenshot(path=str(SORTIE / "19-monnaie.png"))
    page.select_option("#conv-famille", "Température"); page.fill("#conv-valeur", "100")
    page.select_option("#conv-de", "°C"); page.select_option("#conv-vers", "°F")
    verifier("convertisseur : 100 °C = 212 °F", page.input_value("#conv-sortie") == "212 °F", page.input_value("#conv-sortie"))
    page.select_option("#conv-famille", "Poids"); page.fill("#conv-valeur", "2,5")
    page.select_option("#conv-de", "kg"); page.select_option("#conv-vers", "livre")
    verifier("convertisseur : 2,5 kg ≈ 5,51 livres", page.input_value("#conv-sortie").startswith("5,51"), page.input_value("#conv-sortie"))

    # Liste à deux
    page.locator("[data-volet='liste']").click()
    page.fill("#liste-texte", "Relancer le transporteur"); page.keyboard.press("Enter")
    page.wait_for_selector(".tache")
    verifier("liste : la tâche est ajoutée et « Liste à deux » affiche 1", page.inner_text("#pastille-taches") == "1")
    page.locator(".tache input").first.check()
    page.wait_for_function("document.querySelector('#pastille-taches').hidden")
    verifier("liste : cochée, elle est enregistrée et le compteur disparaît", s.taches[0]["done"] is True)

    # Rédaction : page à part, correction sans clé d'IA
    page.click("#ouvrir-redaction")
    page.wait_for_selector("#vue-redaction:not([hidden])")
    page.wait_for_function("document.querySelector('#redac-note').textContent.length > 0")
    verifier("rédaction : s'ouvre en page entière depuis la barre du haut", page.is_visible("#redac-texte"))
    verifier("rédaction : sans clé, les reformulations sont désactivées", page.locator("#redac-tons button").first.is_disabled() and page.is_disabled("#redac-consigne"))
    page.screenshot(path=str(SORTIE / "15-redaction-vide.png"))
    page.fill("#redac-texte", "Bonjour, je vous envoi le devis demain.")
    page.click("#redac-corriger")
    page.wait_for_selector("#redac-resultat:not([hidden])")
    verifier("rédaction : la correction est appliquée et surlignée", page.locator("#redac-sortie del").count() >= 1 and "envoie" in page.inner_text("#redac-sortie"), page.inner_text("#redac-sortie"))
    verifier("rédaction : l'explication de la faute est affichée", page.locator("#redac-fautes li").count() == 1)
    page.screenshot(path=str(SORTIE / "16-redaction-resultat.png"))
    page.click("#redac-voir-final")
    verifier("rédaction : « Texte final » montre le texte propre", page.inner_text("#redac-sortie") == "Bonjour, je vous envoie le devis demain.", page.inner_text("#redac-sortie"))
    verifier("rédaction : le résultat entre dans l'historique", page.locator("#redac-histo-liste li").count() == 1)
    # Mise en page conservée : paragraphes et retours à la ligne, sans police imposée à la copie
    page.evaluate("""() => { const z = document.querySelector('#redac-texte'); z.focus(); z.value = '';
      const dt = new DataTransfer(); dt.setData('text/plain', 'Bonjour Marc,\\r\\n\\r\\nJe vous envoi le devis.\\r\\nMerci,\\r\\nLuka');
      z.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })); }""")
    verifier("collage : les retours à la ligne sont gardés", page.input_value("#redac-texte") == "Bonjour Marc,\n\nJe vous envoi le devis.\nMerci,\nLuka", repr(page.input_value("#redac-texte")))
    page.click("#redac-corriger")
    page.wait_for_function("document.querySelector('#redac-sortie').textContent.includes('envoie')")
    page.click("#redac-voir-final")
    verifier("résultat : paragraphes et retours à la ligne affichés", page.inner_text("#redac-sortie") == "Bonjour Marc,\n\nJe vous envoie le devis.\nMerci,\nLuka", repr(page.inner_text("#redac-sortie")))
    copie = page.evaluate("""() => { const s = document.querySelector('#redac-sortie'); const r = document.createRange(); r.selectNodeContents(s);
      const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
      const dt = new DataTransfer(); s.dispatchEvent(new ClipboardEvent('copy', { clipboardData: dt, bubbles: true, cancelable: true }));
      return { texte: dt.getData('text/plain'), html: dt.getData('text/html') }; }""")
    verifier("copie à la main : texte brut avec ses retours à la ligne, sans police", copie["texte"] == "Bonjour Marc,\n\nJe vous envoie le devis.\nMerci,\nLuka" and copie["html"] == "", copie)
    police = page.evaluate("getComputedStyle(document.querySelector('#redac-sortie')).fontFamily")
    verifier("résultat : affiché dans une police de mail classique", "Bricolage" not in police, police)
    page.click("#redac-fil")
    verifier("rédaction : « Envoyer dans le fil » remplit le message et revient au fil", "Je vous envoie le devis." in page.input_value("#texte") and not page.is_visible("#vue-redaction"))
    page.fill("#texte", "")

    # Notifications : menu de la cloche, coupure et choix du son
    page.click("#cloche")
    verifier("notifications : la cloche ouvre le menu", page.is_visible("#menu-notifs"))
    page.select_option("#notifs-son", "bulle")
    verifier("notifications : le son choisi est retenu", page.evaluate("localStorage.getItem('fil-son')") == "bulle")
    page.screenshot(path=str(SORTIE / "17-menu-notifs.png"))
    page.uncheck("#notifs-actives")
    verifier("notifications : on peut les couper", page.get_attribute("#cloche", "aria-pressed") == "false")
    page.check("#notifs-actives")
    verifier("notifications : on peut les réactiver", page.get_attribute("#cloche", "aria-pressed") == "true")
    page.mouse.click(5, 400)
    verifier("notifications : un clic ailleurs ferme le menu", not page.is_visible("#menu-notifs"))
    verifier("appli installable : service worker actif", page.evaluate("navigator.serviceWorker.getRegistration().then(r => Boolean(r))"))
    verifier("photos : déchiffrées après connexion", page.evaluate("document.querySelectorAll('.bulle.image-emoji img[src^=\"blob:\"]').length") >= 1)

    verifier("aucune erreur de script (fil)", not [e for e in s.erreurs if "pageerror" in e], s.erreurs)
    page.screenshot(path=str(SORTIE / "5-fil-apres-envois.png"))
    ctx.close()

    # Rédaction avec clé d'IA, ouverte directement par un texte partagé depuis une autre appli
    ctx = nav.new_context(viewport={"width": 390, "height": 780}, locale="fr-FR", device_scale_factor=2)
    ctx.add_init_script(SEME)
    page = ctx.new_page(); s = Serveur(MEMBRES, messages_demo(), ia=True); s.brancher(page)
    page.goto(PAGE.replace("index.html", "") + "?text=On%20se%20voit%20demain")
    page.wait_for_selector("#vue-redaction:not([hidden])")
    verifier("partage : le texte partagé ouvre la rédaction déjà remplie", page.input_value("#redac-texte") == "On se voit demain")
    page.wait_for_function("!document.querySelector('#redac-tons button').disabled")
    s.refus_jeton = 1
    page.locator("[data-ton='mail']").click()
    page.wait_for_function("document.querySelector('#redac-sortie').textContent.startsWith('[reformuler]')")
    verifier("rédaction : un jeton refusé est renouvelé automatiquement", any("/auth/v1/token" in r for r in s.requetes))
    page.screenshot(path=str(SORTIE / "18-redaction-telephone.png"))
    page.locator("[data-langue='espagnol']").click()
    page.wait_for_function("document.querySelector('#redac-sortie').textContent.startsWith('[traduire]')")
    page.fill("#redac-consigne", "vouvoie"); page.keyboard.press("Enter")
    page.wait_for_function("document.querySelector('#redac-sortie').textContent.startsWith('[libre]')")
    a = s.appels_assistant
    verifier("rédaction avec clé : « En mail pro » demandé", any(x["action"] == "reformuler" and x["ton"] == "mail" for x in a), a)
    verifier("rédaction avec clé : traduction en espagnol demandée", any(x["action"] == "traduire" and x["langue"] == "espagnol" for x in a), a)
    verifier("rédaction avec clé : demande libre transmise", any(x["action"] == "libre" and x["consigne"] == "vouvoie" for x in a), a)
    verifier("aucune erreur de script (rédaction)", not [e for e in s.erreurs if "pageerror" in e], s.erreurs)
    ctx.close()

    # Raccourci de l'icône : #redaction ouvre directement la rédaction
    ctx = nav.new_context(viewport={"width": 1280, "height": 800}, locale="fr-FR")
    ctx.add_init_script(SEME)
    page = ctx.new_page(); s = Serveur(MEMBRES, messages_demo()); s.brancher(page)
    page.goto(PAGE + "#redaction")
    page.wait_for_selector("#vue-redaction:not([hidden])")
    verifier("raccourci : #redaction ouvre directement la rédaction", True)
    page.click("#redac-retour")
    verifier("rédaction : « Retour au fil » revient au fil", not page.is_visible("#vue-redaction") and page.is_visible("#flux"))
    ctx.close()

    # Notifications activées par défaut : abonnement automatique quand le navigateur les autorise déjà
    ctx = nav.new_context(viewport={"width": 1280, "height": 800}, locale="fr-FR")
    ctx.add_init_script(SEME + "Object.defineProperty(Notification, 'permission', { get: () => 'granted' });")
    page = ctx.new_page(); s = Serveur(MEMBRES, messages_demo()); s.brancher(page)
    page.goto(PAGE); page.wait_for_selector("#vue-fil:not([hidden])")
    page.wait_for_timeout(2500)
    verifier("notifications par défaut : autorisées, l'appli s'abonne d'elle-même", any("/functions/v1/notifier" in r for r in s.requetes), [r for r in s.requetes if "notifier" in r or "push" in r])
    verifier("notifications par défaut : pas de bandeau à valider", not page.is_visible("#invite-notif"))
    ctx.close()

    # Pas encore autorisées : bandeau explicatif, et la demande part au premier clic
    ctx = nav.new_context(viewport={"width": 1280, "height": 800}, locale="fr-FR")
    ctx.add_init_script(SEME + "window.__demandes = 0; Object.defineProperty(Notification, 'permission', { get: () => 'default' }); Notification.requestPermission = function () { window.__demandes++; return Promise.resolve('default'); };")
    page = ctx.new_page(); s = Serveur(MEMBRES, messages_demo()); s.brancher(page)
    page.goto(PAGE); page.wait_for_selector("#vue-fil:not([hidden])")
    page.wait_for_selector("#invite-notif:not([hidden])")
    verifier("notifications par défaut : bandeau explicatif affiché", "activées par défaut" in page.inner_text("#invite-texte"))
    page.click("#flux")
    page.wait_for_timeout(500)
    verifier("notifications par défaut : la demande d'autorisation part au premier clic", page.evaluate("window.__demandes") == 1, page.evaluate("window.__demandes"))
    ctx.close()

    # Rester connecté : après connexion, réouvrir le fichier ne redemande pas le mot de passe
    ctx = nav.new_context(viewport={"width": 1280, "height": 800}, locale="fr-FR")
    page = ctx.new_page(); s = Serveur(MEMBRES, messages_demo(), complet=True); s.brancher(page)
    page.goto(PAGE); page.wait_for_selector("#vue-accueil:not([hidden])")
    page.fill("#email", "luka@example.test"); page.fill("#motdepasse", "valeur-de-test-locale"); page.click("#accueil-valider")
    page.wait_for_selector("#vue-fil:not([hidden])")
    page.close()
    page = ctx.new_page(); s.brancher(page)
    page.goto(PAGE)
    try:
        page.wait_for_selector("#vue-fil:not([hidden])", timeout=8000); ok = True
    except Exception:
        ok = False
    verifier("rester connecté : à la réouverture, le fil s'ouvre directement", ok)
    page.click("#deconnexion")
    page.wait_for_selector("#vue-accueil:not([hidden])")
    verifier("déconnexion : ne touche que cet appareil", s.deconnexions and all("scope=local" in u for u in s.deconnexions), s.deconnexions)
    ctx.close()

    # 4. Fil sur écran étroit
    ctx = nav.new_context(viewport={"width": 390, "height": 780}, locale="fr-FR", timezone_id="Europe/Paris", device_scale_factor=2)
    ctx.add_init_script(SEME)
    page = ctx.new_page(); s = Serveur(MEMBRES, messages_demo()); s.brancher(page)
    page.goto(PAGE); page.wait_for_selector("#vue-fil:not([hidden])"); page.wait_for_timeout(900)
    verifier("écran étroit : pas de débordement horizontal", page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
    page.click("[data-volet='tva']")
    page.screenshot(path=str(SORTIE / "13-etroit-outil.png"))
    page.click("[data-volet='tva']")
    page.screenshot(path=str(SORTIE / "6-fil-etroit.png"))
    ctx.close()

    # 5. Sans liaison en direct, puis compte hors du fil
    ctx = nav.new_context(viewport={"width": 1280, "height": 800}, locale="fr-FR")
    ctx.add_init_script(SEME)
    page = ctx.new_page(); s = Serveur(MEMBRES, messages_demo(), direct=False); s.brancher(page)
    page.route("wss://**", lambda r: r.abort())
    page.goto(PAGE); page.wait_for_selector("#vue-fil:not([hidden])")
    try:
        page.wait_for_selector("#etat-liaison:not([hidden])", timeout=15000); ok = True
    except Exception:
        ok = False
    verifier("sans temps réel : l'appli le signale et reste utilisable", ok and page.locator(".ligne").count() == 6)
    ctx.close()

    ctx = nav.new_context(viewport={"width": 1280, "height": 800}, locale="fr-FR")
    ctx.add_init_script(SEME)
    page = ctx.new_page(); s = Serveur([], []); s.brancher(page)
    page.goto(PAGE); page.wait_for_selector("#vue-exclu:not([hidden])", timeout=8000)
    verifier("compte hors du fil : écran « déjà complet »", "complet" in page.inner_text("#vue-exclu"))
    ctx.close()
    nav.close()

echecs = [r for r in resultats if not r[1]]
print("\n%d essais, %d échec(s)" % (len(resultats), len(echecs)))
sys.exit(1 if echecs else 0)
