// Assemble le site du fil dans dist/site : la page (avec la bibliothèque Supabase intégrée),
// les photos chiffrées (clé lisible seulement par les deux membres), le service worker, le manifeste et les icônes.
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const racine = __dirname;
const sortie = path.join(racine, "dist/site");
let page = fs.readFileSync(path.join(racine, "src/index.html"), "utf8");

function remplacer(marqueur, valeur) {
  if (!page.includes(marqueur)) throw new Error("marqueur absent : " + marqueur);
  page = page.replace(marqueur, () => valeur);
}

let lib = fs.readFileSync(path.join(racine, "node_modules/@supabase/supabase-js/dist/umd/supabase.js"), "utf8");
lib = lib.replace(/<\/script/gi, "<\\/script");
remplacer("/*__SUPABASE_UMD__*/", lib);

// Photos chiffrées (AES-256-GCM). La clé (.cle-decor) et les photos en clair (images/) ne sont jamais publiées.
// Sans elles, l'assemblage reprend la version déjà chiffrée : decor-chiffre.json.
const fichierCle = path.join(racine, ".cle-decor");
const fichierDecor = path.join(racine, "decor-chiffre.json");
let decor;
if (fs.existsSync(fichierCle) && fs.existsSync(path.join(racine, "images"))) {
  const cle = Buffer.from(fs.readFileSync(fichierCle, "utf8").trim(), "base64");
  if (cle.length !== 32) throw new Error("clé du décor invalide");
  const b64url = (x) => x.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const chiffrer = (fichier) => {
    const iv = crypto.randomBytes(12);
    const c = crypto.createCipheriv("aes-256-gcm", cle, iv);
    const d = Buffer.concat([c.update(fs.readFileSync(fichier)), c.final(), c.getAuthTag()]);
    return { iv: b64url(iv), d: b64url(d) };
  };
  decor = { magie: {}, image: {} };
  for (const nom of ["melon", "david", "occupe", "dj", "mail", "gregr", "kiki", "top"]) {
    decor.magie[nom] = chiffrer(path.join(racine, "images", nom + ".webp"));
  }
  for (const nom of ["porsche", "newyork", "bracelet", "oslo", "melon", "david"]) {
    decor.image[nom] = chiffrer(path.join(racine, "images", "s-" + nom + ".webp"));
  }
  fs.writeFileSync(fichierDecor, JSON.stringify(decor));
} else {
  decor = JSON.parse(fs.readFileSync(fichierDecor, "utf8"));
}
remplacer("/*__DECOR__*/{}", JSON.stringify(decor));

fs.rmSync(sortie, { recursive: true, force: true });
fs.mkdirSync(sortie, { recursive: true });
fs.writeFileSync(path.join(sortie, "index.html"), page);
for (const f of fs.readdirSync(path.join(racine, "public"))) {
  fs.copyFileSync(path.join(racine, "public", f), path.join(sortie, f));
}
// Évite que GitHub Pages traite le site avec Jekyll
fs.writeFileSync(path.join(sortie, ".nojekyll"), "");
console.log("ok", (page.length / 1024).toFixed(0) + " Ko", fs.readdirSync(sortie).join(", "));
