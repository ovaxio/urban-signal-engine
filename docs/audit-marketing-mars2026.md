# Urban Signal Engine — Audit Produit & Go-To-Market
**Date** : Mars 2026 — Usage interne : Marketing / Stratégie / Vente

---

## 1. C'est quoi

**Urban Signal Engine** est une API SaaS de scoring de tension urbaine en temps réel pour la ville de Lyon.

- Score 0-100 par zone (12 zones couvertes : Part-Dieu, Presqu'île, Vieux-Lyon, Perrache, Gerland, Guillotière, Brotteaux, Villette, Montchat, Fourvière, Croix-Rousse, Confluence)
- Mise à jour toutes les 60 secondes, alimentée par 5 sources de données ouvertes (trafic, incidents, transports, météo, événements)
- Prévision sur 6 horizons (30 min → 24h)
- Rapports d'impact post-événement + pré-événement avec recommandations opérationnelles

**Positionnement** : outil d'aide à la décision pour les acteurs qui gèrent des ressources humaines ou logistiques sur la voie publique lyonnaise.

---

## 2. Ce qui est livré aujourd'hui

### Produit fonctionnel
| Fonctionnalité | État |
|---|---|
| Score temps réel (12 zones) | ✅ En prod |
| Prévision 6 horizons | ✅ En prod |
| Historique des scores | ✅ En prod |
| Alertes seuil (TENDU / CRITIQUE) | ✅ En prod |
| Rapport post-événement (PDF) | ✅ En prod |
| Rapport pré-événement + recommandations DPS | ✅ En prod |
| Backtest OL match 8 mars 2026 | ✅ Généré, disponible |
| Dashboard web temps réel | ✅ En prod |
| Landing page avec tarifs | ✅ En prod |
| API clés (gestion admin) | ✅ En prod |

### Validation technique
- Backtest validé sur match OL vs Nantes (8 mars 2026) : pics de tension cohérents avec l'événement réel
- Modèle de scoring calibré automatiquement chaque semaine
- Signal transport corrigé (bug d'inflation résolu en mars 2026)
- Déployé sur Render (backend) + Vercel (frontend), disponible 24/7

---

## 3. Modèle commercial

### Offre

| Produit | Prix | Format |
|---|---|---|
| **Rapport Événement** | 390 € HT | One-shot, à la commande |
| **Abonnement Mensuel** | 490 € HT/mois | Accès dashboard + alertes + rapports illimités |
| **API Logistique** | 149 € HT/mois | Accès programmatique (lancement semaine 6+) |

### Logique d'acquisition
1. Entrée par le **rapport événement** (pas de pilote gratuit — décision ferme)
2. Après 2-3 rapports → proposition d'abonnement mensuel
3. Objectif LTV : abonnement à 490€/mois = 5 880 € HT/an par client

---

## 4. Cibles prioritaires

### Segment principal : Sécurité privée & événementielle
- **Profil** : Coordinateurs sécurité, responsables opérations événementielles
- **Exemples** : Securitas Event, SAMSIC Event, GL Events, prestataires sécurité OL/LDLC Arena
- **Déclencheur d'achat** : événement à venir à Lyon (concert, match, salon, manifestation)
- **Valeur perçue** : anticipation du niveau de tension zone par zone → calibration DPS, positionnement agents

### Segment secondaire (à partir de la semaine 6) : Logistique & livraison
- **Profil** : Responsables opérations, dispatch
- **Exemples** : Amazon Last Mile, Stuart, Chronopost Lyon
- **Valeur perçue** : éviter les zones critiques, optimiser les tournées en temps réel

### Segments explicitement exclus (décision stratégique)
- Collectivités publiques (cycles longs, marchés publics)
- Sécurité publique / police (souveraineté, budget spécifique)
- Assureurs, immobilier (besoin non validé)
- Retail (cas d'usage trop éloigné)

---

## 5. Preuves disponibles pour les prospects

| Preuve | Format | Disponibilité |
|---|---|---|
| Backtest OL 8 mars 2026 | PDF | Disponible maintenant |
| Dashboard live Lyon | Web (URL) | Disponible 24/7 |
| Rapport pré-événement exemple | PDF généré à la demande | Sur demande |
| Rapport post-événement exemple | PDF généré à la demande | Sur demande |

**Argument clé** : le système a correctement anticipé la montée en tension autour de Gerland et Guillotière avant et pendant le match OL — sans connaissance préalable du résultat.

---

## 6. Ce qui manque pour accélérer les ventes

| Besoin | Priorité | Commentaire |
|---|---|---|
| Premier client payant signé | 🔴 Critique | Débloque tout (référence, cashflow, validation) |
| Deck commercial 1 page | 🟠 Haute | À créer — base = ce document |
| Séquence email outreach sécurité événementielle | 🟠 Haute | 10-15 cibles identifiables sur LinkedIn Lyon |
| Page "Cas d'usage" avec backtest OL intégré | 🟡 Moyenne | Landing page partielle, backtest non mis en avant |
| Témoignage / devis signé | 🟡 Moyenne | Après premier contact |

---

## 7. Positionnement concurrentiel

**Il n'existe pas d'outil équivalent à Lyon** (ni en France à notre connaissance) qui combine :
- données temps réel multi-sources
- scoring normalisé par zone urbaine
- rapport opérationnel prêt à l'emploi

Les alternatives actuelles des prospects : feeling terrain, expérience passée, échanges radio. Urban Signal Engine remplace ou complète ces pratiques avec de la donnée quantifiée.

---

## 8. Risques à avoir en tête

| Risque | Niveau | Mitigation |
|---|---|---|
| Adoption lente (éducation marché) | Moyen | Rapport one-shot à 390€ = ticket d'entrée bas |
| Dépendance aux APIs externes (Grand Lyon, Open-Meteo) | Faible | Sources ouvertes stables, pas de quota critique |
| Scalabilité SQLite | Faible | Acceptable jusqu'au premier client payant, migration planifiée ensuite |
| Crédibilité sans référence client | Élevé | Backtest + démo live compensent à court terme |

---

*Document généré le 21 mars 2026 — Urban Signal Engine MVP*
