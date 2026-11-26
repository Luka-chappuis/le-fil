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
        self.diffusions, self.modifs, self.coupure = [], [], False
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
        if self.coupure:
            return route.abort("internetdisconnected")
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
                if donnees.get("client_id") and any(m.get("client_id") == donnees["client_id"] for m in self.messages):
                    return js({"code": "23505", "message": "doublon"}, 409)
                nouveau.update(donnees)
                self.messages.append(nouveau)
                return js(nouveau, 201)
            if methode == "PATCH":
                ident = int(url.split("id=eq.")[1].split("&")[0])
                d = json.loads(req.post_data)
                for m in self.messages:
                    if m["id"] == ident:
                        m.update(d); m["edited_at"] = "2026-11-26T16:00:00+00:00"; self.modifs.append(d)
                        return js(m)
                return js({"message": "introuvable"}, 404)
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
            if methode == "PATCH":
                d = json.loads(req.post_data)
                for m in self.mots:
                    if "id=eq.%d" % m["id"] in url:
                        m.update(d); return js(m)
                return js({"message": "introuvable"}, 404)
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
        if isinstance(brut, (bytes, bytearray)):   # diffusion binaire (« écrit… »)
            self.diffusions.append(bytes(brut)); return
        m = json.loads(brut)
        if (m.get("event") if isinstance(m, dict) else (m[3] if len(m) > 3 else None)) == "broadcast":
            self.diffusions.append(brut)
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

def msg(i, qui, **k):
    m = {"id": i, "sender": qui, "body": None, "file_path": None, "file_name": None, "file_size": None, "file_type": None,
         "created_at": "2026-11-26T10:%02d:00+01:00" % i, "reply_to": None, "edited_at": None, "client_id": None}
    m.update(k); return m

def demo_v8():
    return [
        msg(1, JULES, body="Salut ! Tu as le devis du transporteur ?"),
        msg(2, LUKA, file_path=LUKA + "/p.png", file_name="Photo stand.png", file_size=50000, file_type="image/png", body="Le stand hier"),
        msg(3, LUKA, body="Oui, je te l'envoie ce soir.", reply_to=1),
        msg(4, JULES, file_path=JULES + "/v.m4a", file_name="Message vocal.m4a", file_size=30000, file_type="audio/mp4"),
        msg(5, JULES, body="Parfait merci", edited_at="2026-11-26T10:06:00+01:00"),
        msg(6, LUKA, file_path=LUKA + "/d.pdf", file_name="Devis transport.pdf", file_size=184320, file_type="application/pdf"),
    ]

def diffuser_ecrit(s):
    for ws in s.sockets:
        s.envoyer(ws, ws._sujet, "broadcast", {"type": "broadcast", "event": "ecrit", "payload": {"qui": JULES}})

with sync_playwright() as p:
    nav = p.chromium.launch()
    ctx = nav.new_context(viewport={"width": 1280, "height": 800}, locale="fr-FR", timezone_id="Europe/Paris")
    ctx.add_init_script(SEME)
    page = ctx.new_page(); s = Serveur(MEMBRES, demo_v8()); s.brancher(page)
    page.goto(PAGE); page.wait_for_selector("#vue-fil:not([hidden])"); page.wait_for_timeout(1200)
    verifier("photo : vignette affichée dans la bulle", page.locator(".bulle.photo .photo-bouton img[src]").count() == 1)
    verifier("photo : légende sous la vignette", "Le stand hier" in page.inner_text(".bulle.photo"))
    verifier("vocal : lecteur audio", page.locator(".bulle.vocal audio[src]").count() == 1)
    verifier("pdf : toujours une fiche avec boutons", page.locator(".fichier-actions button").count() == 2)
    verifier("réponse : citation du message d'origine", "Tu as le devis" in page.inner_text(".ligne[data-id='3'] .citation"))
    verifier("modifié : mention affichée", page.locator(".ligne[data-id='5'] .modifie").count() == 1)
    verifier("modifier : proposé sur mes textes et mes photos, pas sur ceux de Jules", page.locator(".ligne[data-id='3'] >> text=Modifier").count() == 1 and page.locator(".ligne[data-id='5'] >> text=Modifier").count() == 0 and page.locator(".ligne[data-id='2'] >> text=Modifier").count() == 1)
    page.screenshot(path=str(SORTIE / "v8-1-fil.png"))

    page.click(".photo-bouton")
    verifier("visionneuse : ouverte avec la photo", page.is_visible("#visionneuse") and page.get_attribute("#visionneuse-image", "src"))
    page.wait_for_timeout(200); page.screenshot(path=str(SORTIE / "v8-2-visionneuse.png"))
    page.keyboard.press("Escape")
    verifier("visionneuse : fermée par Échap", not page.is_visible("#visionneuse"))

    # Réponse
    page.click(".ligne[data-id='1'] >> text=Répondre")
    verifier("réponse : bandeau au-dessus de la saisie", page.is_visible("#bandeau") and "Jules" in page.inner_text("#bandeau"))
    page.screenshot(path=str(SORTIE / "v8-3-bandeau.png"))
    page.fill("#texte", "Je regarde ça"); page.keyboard.press("Enter"); page.wait_for_timeout(500)
    dernier = s.messages[-1]
    verifier("réponse : envoyée avec reply_to et client_id", dernier.get("reply_to") == 1 and len(dernier.get("client_id") or "") == 36, dernier)
    verifier("réponse : bandeau refermé", not page.is_visible("#bandeau"))
    verifier("réponse : citation dans la nouvelle bulle", page.locator(".ligne[data-id='%d'] .citation" % dernier["id"]).count() == 1)

    # Modification
    page.click(".ligne[data-id='3'] >> text=Modifier")
    verifier("modifier : texte repris dans la saisie", page.input_value("#texte") == "Oui, je te l'envoie ce soir.")
    page.fill("#texte", "Oui, je te l'envoie demain."); page.keyboard.press("Enter"); page.wait_for_timeout(500)
    verifier("modifier : enregistré sur le serveur", s.modifs and s.modifs[-1].get("body") == "Oui, je te l'envoie demain.", s.modifs)
    verifier("modifier : bulle mise à jour et marquée", "demain" in page.inner_text(".ligne[data-id='3']") and page.locator(".ligne[data-id='3'] .modifie").count() == 1)
    verifier("modifier : saisie vidée", page.input_value("#texte") == "")
    page.click(".ligne[data-id='3'] >> text=Modifier"); page.keyboard.press("Escape")
    verifier("modifier : Échap annule et vide la saisie", not page.is_visible("#bandeau") and page.input_value("#texte") == "")

    # Légende d'une photo
    page.click(".ligne[data-id='2'] >> text=Modifier")
    verifier("modifier photo : choix entre le texte et l'image", page.locator(".ligne[data-id='2'] .choix-modif button").count() == 2)
    page.screenshot(path=str(SORTIE / "v8-3b-choix.png"))
    page.click(".ligne[data-id='2'] >> text=Le texte")
    verifier("légende : texte de la photo repris", page.input_value("#texte") == "Le stand hier" and "Légende" in page.inner_text("#bandeau"))
    page.fill("#texte", "Le stand avant l'ouverture"); page.keyboard.press("Enter"); page.wait_for_timeout(500)
    verifier("légende : modifiée sous la photo", "avant l'ouverture" in page.inner_text(".ligne[data-id='2'] .bulle.photo") and page.locator(".ligne[data-id='2'] .photo-bouton img").count() == 1)
    page.click(".ligne[data-id='2'] >> text=Modifier"); page.click(".ligne[data-id='2'] >> text=Le texte"); page.fill("#texte", ""); page.keyboard.press("Enter"); page.wait_for_timeout(500)
    verifier("légende : peut être retirée", s.modifs[-1].get("body") is None and page.locator(".ligne[data-id='2'] .legende").count() == 0, s.modifs[-1])
    ancien = page.get_attribute(".ligne[data-id='2'] .photo-bouton img", "src")
    page.click(".ligne[data-id='2'] >> text=Modifier")
    with page.expect_file_chooser() as fc:
        page.click(".ligne[data-id='2'] >> text=L'image")
    fc.value.set_files(files=[{"name": "nouvelle.png", "mimeType": "image/png", "buffer": PNG_ESSAI}])
    page.wait_for_timeout(800)
    m2 = [m for m in s.messages if m["id"] == 2][0]
    verifier("remplacer l'image : message mis à jour", m2["file_name"] == "nouvelle.png" and m2["file_path"] != LUKA + "/p.png" and m2["file_path"].startswith(LUKA + "/"), m2)
    verifier("remplacer l'image : ancienne image supprimée du stockage", LUKA + "/p.png" in s.fichiers_retires, s.fichiers_retires)
    verifier("remplacer l'image : nouvelle vignette affichée", page.locator(".ligne[data-id='2'] .photo-bouton img[src]").count() == 1 and page.locator(".ligne[data-id='2'] .modifie").count() == 1)
    page.set_input_files("#selecteur", files=[{"name": "plan.png", "mimeType": "image/png", "buffer": PNG_ESSAI}])
    page.fill("#texte", "Le plan final"); page.keyboard.press("Enter"); page.wait_for_timeout(800)
    dernier = s.messages[-1]
    verifier("légende : texte + une photo = un seul message", dernier.get("file_name") == "plan.png" and dernier.get("body") == "Le plan final" and not any(m.get("body") == "Le plan final" and not m.get("file_path") for m in s.messages), dernier)

    # « écrit… »
    page.wait_for_timeout(2700); avant = len(s.diffusions)
    page.type("#texte", "salut", delay=30); page.wait_for_timeout(300)
    verifier("écrit : signal envoyé pendant la frappe", len(s.diffusions) > avant, len(s.diffusions))
    page.fill("#texte", "")
    diffuser_ecrit(s); page.wait_for_timeout(300)
    verifier("écrit : « Jules écrit » affiché", page.is_visible("#ecrit") and "Jules écrit" in page.inner_text("#ecrit"))
    page.screenshot(path=str(SORTIE / "v8-4-ecrit.png"))
    s.pousser_message(msg(20, JULES, body="Top")); page.wait_for_timeout(400)
    verifier("écrit : disparaît à l'arrivée du message", not page.is_visible("#ecrit"))

    # Recherche
    page.click("#ouvrir-recherche")
    page.fill("#recherche-saisie", "devis"); page.keyboard.press("Enter"); page.wait_for_timeout(500)
    n = page.locator("#resultats li").count()
    verifier("recherche : messages et fichiers trouvés", n == 2, n)
    verifier("recherche : mot surligné", page.locator("#resultats mark").count() >= 1)
    page.screenshot(path=str(SORTIE / "v8-5-recherche.png"))
    page.locator("#resultats button").last.click(); page.wait_for_timeout(300)
    verifier("recherche : retour au fil sur le message", not page.is_visible("#vue-recherche") and page.locator(".ligne[data-id='1'].surligne").count() == 1)

    # Envoi différé
    ctx.set_offline(True); s.coupure = True
    page.fill("#texte", "Envoyé dans le tunnel"); page.keyboard.press("Enter"); page.wait_for_timeout(600)
    verifier("hors ligne : message gardé en attente", page.locator(".ligne.pas-envoye").count() == 1 and not any(m.get("body") == "Envoyé dans le tunnel" for m in s.messages))
    page.screenshot(path=str(SORTIE / "v8-6-attente.png"))
    garde = page.evaluate("localStorage.getItem('le-fil-file-attente')") or ""
    verifier("hors ligne : gardé en mémoire (survit à la fermeture)", "Envoyé dans le tunnel" in garde, garde)
    ctx.set_offline(False); s.coupure = False; page.evaluate("window.dispatchEvent(new Event('online'))"); page.wait_for_timeout(1200)
    envoyes = [m for m in s.messages if m.get("body") == "Envoyé dans le tunnel"]
    verifier("hors ligne : parti au retour de la connexion, une seule fois", len(envoyes) == 1, len(envoyes))
    verifier("hors ligne : plus marqué en attente", page.locator(".ligne.pas-envoye").count() == 0)

    # Mots magiques : modifier le mot ou l'image
    s.mots.append({"id": 500, "mot": "lydie", "image_path": JULES + "/magie/a.webp", "created_by": JULES, "created_at": "2026-11-26T15:00:00Z"})
    s.mots.append({"id": 501, "mot": "apéro", "image_path": LUKA + "/magie/b.webp", "created_by": LUKA, "created_at": "2026-11-26T15:01:00Z"})
    page.click("#ouvrir-reglages"); page.wait_for_timeout(600)
    ligne = page.locator(".mot-ligne", has_text="lydie")
    ligne.locator("text=Modifier").click()
    verifier("mot magique : choix entre le mot et l'image", ligne.locator(".choix-modif button").count() == 2)
    page.screenshot(path=str(SORTIE / "v8-10-mot-choix.png"))
    ligne.locator("text=Le mot").click()
    champ = page.locator(".mot-edition input")
    champ.fill("Apero"); page.locator(".mot-edition button[type=submit]").click(); page.wait_for_timeout(200)
    verifier("mot magique : doublon refusé", "existe déjà" in page.inner_text(".mot-edition"))
    champ.fill("Lydie la reine"); page.locator(".mot-edition button[type=submit]").click(); page.wait_for_timeout(500)
    verifier("mot magique : mot modifié", any(m["mot"] == "Lydie la reine" for m in s.mots) and page.locator(".mot-nom", has_text="Lydie la reine").count() == 1)
    ligne = page.locator(".mot-ligne", has_text="Lydie la reine")
    ligne.locator("text=Modifier").click()
    with page.expect_file_chooser() as fc:
        ligne.locator("text=L'image").click()
    fc.value.set_files(files=[{"name": "neuve.png", "mimeType": "image/png", "buffer": PNG_ESSAI}])
    page.wait_for_timeout(1000)
    m500 = [m for m in s.mots if m["id"] == 500][0]
    verifier("mot magique : nouvelle image dans mon dossier", m500["image_path"].startswith(LUKA + "/magie/") and m500["image_path"] != JULES + "/magie/a.webp", m500)
    verifier("mot magique : ancienne image supprimée", JULES + "/magie/a.webp" in s.fichiers_retires, s.fichiers_retires)
    page.click("#reglages-retour")

    verifier("aucune erreur de script", not [e for e in s.erreurs if "pageerror" in e], s.erreurs)

    # Apparence : clair par défaut, sombre au choix
    page.emulate_media(color_scheme="dark"); page.wait_for_timeout(200)
    fond = page.evaluate("getComputedStyle(document.body).backgroundColor")
    verifier("apparence : reste claire même si l'appareil est en sombre", fond == "rgb(237, 242, 241)", fond)
    page.click("#ouvrir-reglages"); page.click("[data-theme-choix='sombre']"); page.wait_for_timeout(200)
    page.screenshot(path=str(SORTIE / "v8-7-reglages-sombre.png"))
    page.click("#reglages-retour")
    fond = page.evaluate("getComputedStyle(document.body).backgroundColor")
    verifier("apparence : sombre une fois choisi", fond == "rgb(15, 27, 30)", fond)
    page.reload(); page.wait_for_selector("#vue-fil:not([hidden])"); page.wait_for_timeout(800)
    fond = page.evaluate("getComputedStyle(document.body).backgroundColor")
    verifier("apparence : choix gardé à la réouverture", fond == "rgb(15, 27, 30)", fond)
    page.screenshot(path=str(SORTIE / "v8-7-sombre.png"))
    page.click("#ouvrir-reglages"); page.click("[data-theme-choix='clair']"); page.click("#reglages-retour")
    fond = page.evaluate("getComputedStyle(document.body).backgroundColor")
    verifier("apparence : retour au clair", fond == "rgb(237, 242, 241)", fond)
    ctx.close()

    ctx = nav.new_context(viewport={"width": 390, "height": 844}, locale="fr-FR", timezone_id="Europe/Paris", is_mobile=True, has_touch=True)
    ctx.add_init_script(SEME)
    page = ctx.new_page(); s = Serveur(MEMBRES, demo_v8()); s.brancher(page)
    page.goto(PAGE); page.wait_for_selector("#vue-fil:not([hidden])"); page.wait_for_timeout(1200)
    page.click(".ligne[data-id='1'] >> text=Répondre")
    page.screenshot(path=str(SORTIE / "v8-8-mobile.png"))
    page.evaluate("document.documentElement.dataset.theme = 'sombre'"); page.wait_for_timeout(200)
    page.screenshot(path=str(SORTIE / "v8-9-mobile-sombre.png"))
    verifier("mobile : aucune erreur de script", not [e for e in s.erreurs if "pageerror" in e], s.erreurs)
    ctx.close(); nav.close()

echecs = [r for r in resultats if not r[1]]
print("\n%d essais, %d échec(s)" % (len(resultats), len(echecs)))
sys.exit(1 if echecs else 0)
