"use strict";

const $ = (id) => document.getElementById(id);
const fr = (n, dec = 2) => new Intl.NumberFormat("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(n);
const dateCourte = (iso) => new Date(iso + "T12:00:00Z").toLocaleDateString("fr-FR", { day: "numeric", month: "short", timeZone: "UTC" });
const dateLongue = (iso) => new Date(iso + "T12:00:00Z").toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

function el(tag, props = {}, ...enfants) {
  const n = document.createElement(tag);
  Object.assign(n, props);
  n.append(...enfants);
  return n;
}

function signe(n, dec = 1) {
  const arrondi = Number(n.toFixed(dec));
  const s = arrondi > 0 ? "+" : arrondi < 0 ? "−" : "";
  return s + fr(Math.abs(arrondi), dec);
}
const formatVar = (i) => i.variation_7j === null || i.variation_7j === undefined
  ? "n.d."
  : i.mode_variation === "pts" ? `${signe(i.variation_7j, 2)} pt` : `${signe(i.variation_7j)} %`;
function formatValeur(i) {
  const dec = i.id === "eurusd" ? 4 : i.valeur >= 1000 ? 0 : 2;
  const v = fr(i.valeur, dec);
  return i.unite === "pts" ? v : `${v} ${i.unite}`;
}
const sens = (i) => {
  if (i.variation_7j == null) return "";
  const arrondi = Number(i.variation_7j.toFixed(i.mode_variation === "pts" ? 2 : 1));
  return arrondi > 0 ? "hausse" : arrondi < 0 ? "baisse" : "";
};

function phrase(instruments) {
  const comparables = instruments.filter((i) => i.mode_variation === "pct" && i.variation_7j != null);
  if (!comparables.length) return "Les variations sur sept jours ne sont pas encore disponibles.";
  const tries = [...comparables].sort((a, b) => b.variation_7j - a.variation_7j);
  const hausses = comparables.filter((i) => sens(i) === "hausse").length;
  const nb = comparables.length;
  const debut = `En sept jours, ${hausses} marché${hausses > 1 ? "s" : ""} sur ${nb} ${hausses > 1 ? "ont" : "a"} monté.`;
  const haut = tries[0], bas = tries[nb - 1];
  const details = [];
  if (sens(haut) === "hausse") details.push(`${haut.nom} progresse le plus (${formatVar(haut)})`);
  if (sens(bas) === "baisse") details.push(`${bas.nom} recule le plus (${formatVar(bas)})`);
  return details.length ? `${debut} ${details.join(", ")}.` : debut;
}

function classement(instruments) {
  const lignes = instruments
    .filter((i) => i.mode_variation === "pct" && i.variation_7j != null)
    .sort((a, b) => b.variation_7j - a.variation_7j);
  const boite = $("classement");
  if (!lignes.length) return;
  const max = Math.max(...lignes.map((i) => Math.abs(i.variation_7j)), 0.1);
  for (const i of lignes) {
    const barre = el("div", { className: `barre ${sens(i)}` });
    barre.style.width = `${(Math.abs(i.variation_7j) / max) * 50}%`;
    const piste = el("div", { className: "piste" }, barre);
    piste.setAttribute("aria-hidden", "true");
    boite.append(el("div", { className: "rang" },
      el("span", { className: "rang-nom", textContent: i.nom, title: i.nom }),
      piste,
      el("span", { className: "rang-val", textContent: formatVar(i) })));
  }
  boite.append(el("p", { className: "echelle", textContent: "Variation sur sept jours, du plus fort au plus faible. Les taux, exprimés en points, sont dans le tableau ci-dessous." }));
}

function courbe(i) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "courbe");
  svg.setAttribute("aria-hidden", "true");
  const serie = i.serie || [];
  if (serie.length < 2) return svg;
  const L = 120, H = 32, m = 3;
  const vals = serie.map((p) => p[1]);
  const min = Math.min(...vals), max = Math.max(...vals), e = max - min || 1;
  const x = (k) => (k / (serie.length - 1)) * L;
  const y = (v) => m + (1 - (v - min) / e) * (H - 2 * m);
  svg.setAttribute("viewBox", `0 0 ${L} ${H}`);
  svg.setAttribute("preserveAspectRatio", "none");
  const d = serie.map((p, k) => `${k ? "L" : "M"}${x(k).toFixed(1)} ${y(p[1]).toFixed(1)}`).join("");
  const chemin = document.createElementNS(NS, "path");
  chemin.setAttribute("d", d);
  svg.append(chemin);
  const bulle = $("infobulle");
  svg.addEventListener("pointermove", (ev) => {
    const r = svg.getBoundingClientRect();
    const k = Math.round(((ev.clientX - r.left) / r.width) * (serie.length - 1));
    const p = serie[Math.max(0, Math.min(serie.length - 1, k))];
    bulle.textContent = `${dateCourte(p[0])} : ${formatValeur({ ...i, valeur: p[1] })}`;
    bulle.hidden = false;
    bulle.style.left = `${Math.max(8, Math.min(innerWidth - bulle.offsetWidth - 8, ev.clientX - bulle.offsetWidth / 2))}px`;
    bulle.style.top = `${r.top - bulle.offsetHeight - 6}px`;
  });
  svg.addEventListener("pointerleave", () => { bulle.hidden = true; });
  return svg;
}

function tableaux(instruments) {
  const groupes = [...new Set(instruments.map((i) => i.groupe))];
  for (const g of groupes) {
    const corps = el("tbody");
    for (const i of instruments.filter((x) => x.groupe === g)) {
      const nom = el("th", { scope: "row", textContent: i.nom });
      const quand = el("td", { className: "date", textContent: dateCourte(i.date) });
      if (i.statut === "ancien") quand.append(el("span", { className: "ancien", textContent: "source indisponible" }));
      nom.append(el("span", { className: "sous", textContent: `${dateCourte(i.date)}${i.statut === "ancien" ? ", source indisponible" : ""}` }));
      const s = sens(i);
      corps.append(el("tr", {}, nom,
        el("td", { textContent: formatValeur(i) }),
        el("td", { className: s ? `${s}-t` : "", textContent: formatVar(i) }),
        quand,
        el("td", {}, courbe(i))));
    }
    const entete = el("tr", {}, ...["Marché", "Dernier cours", "Sur 7 jours", "Date", "60 dernières séances"]
      .map((t) => el("th", { scope: "col", textContent: t })));
    $("groupes").append(el("div", { className: "groupe defile" },
      el("table", {}, el("caption", { textContent: g }), el("thead", {}, entete), corps)));
  }
}

async function chargerMarche() {
  try {
    const r = await fetch("data/marche.json", { cache: "no-cache" });
    if (!r.ok) throw new Error(String(r.status));
    const d = await r.json();
    $("phrase").textContent = phrase(d.instruments);
    const quand = new Date(d.maj);
    const heures = (Date.now() - quand) / 36e5;
    $("maj").textContent = `Données relevées le ${quand.toLocaleString("fr-FR", { dateStyle: "long", timeStyle: "short" })}.`;
    if (heures > 48) {
      $("maj").textContent += " Le relevé a plus de deux jours : la collecte automatique est peut-être en panne.";
      $("maj").classList.add("alerte");
    }
    classement(d.instruments);
    tableaux(d.instruments);
  } catch {
    $("phrase").textContent = "Les données de marché ne sont pas encore disponibles.";
    $("maj").textContent = "Elles apparaîtront ici après la prochaine collecte automatique.";
  }
}

async function afficherRapport(r) {
  const boite = $("rapport");
  try {
    const rep = await fetch(r.fichier, { cache: "no-cache" });
    if (!rep.ok) throw new Error(String(rep.status));
    boite.innerHTML = DOMPurify.sanitize(marked.parse(await rep.text()));
    boite.querySelectorAll("a[href^='http']").forEach((a) => { a.target = "_blank"; a.rel = "noopener noreferrer"; });
  } catch {
    boite.replaceChildren(el("p", { className: "vide", textContent: `La ronde du ${dateLongue(r.date)} n'a pas pu être chargée. Recharge la page pour réessayer.` }));
  }
}

async function chargerRapports() {
  let liste = [];
  try {
    const r = await fetch("data/rapports.json", { cache: "no-cache" });
    if (r.ok) liste = await r.json();
  } catch { /* traité comme une liste vide */ }
  if (!liste.length) {
    $("rapport").replaceChildren(el("p", { className: "vide", textContent: "Aucune ronde publiée pour l'instant. La prochaine est prévue lundi matin." }));
    return;
  }
  const choix = $("archives");
  for (const r of liste) choix.append(el("option", { value: r.date, textContent: dateLongue(r.date) }));
  $("choix").hidden = liste.length < 2;
  choix.addEventListener("change", () => afficherRapport(liste.find((r) => r.date === choix.value)));
  afficherRapport(liste[0]);
}

chargerMarche();
chargerRapports();
