# Créer un ADR Urban Signal Engine

Sujet : $ARGUMENTS

## Instructions

1. Lire `docs/decisions/README.md` pour trouver le prochain numéro disponible.
2. Lire les ADRs existants les plus proches du sujet pour vérifier qu'il n'y a pas de doublon.
3. Créer le fichier `docs/decisions/ADR-{NNN}-{kebab-case}.md` avec exactement ce format :

```markdown
# ADR-{NNN} — {Titre}

**Date**: {date du jour}
**Status**: Accepted
**Source**: Claude Code session — {description courte de la tâche}

## Decision
{Une ou deux lignes max — la décision exacte}

## Values
{Constantes, paramètres, seuils, règles — en code block ou bullets}

## Rationale
- {Raison non-évidente 1}
- {Raison non-évidente 2}

## Consequences
- {Ce qui est maintenant vrai}
- {Ce qui a changé}

## DO NOT
- {Interdiction explicite 1}
- {Interdiction explicite 2}

## Triggers
Re-read when: {liste de fichiers, fonctions ou topics}
```

Contraintes strictes :
- Max 30 lignes total
- Pas de paragraphes en prose — bullets et phrases courtes uniquement
- Section DO NOT obligatoire (minimum 2 items)
- Section Triggers obligatoire

4. Mettre à jour `docs/decisions/README.md` — ajouter la ligne dans le tableau.
5. Mettre à jour le tableau "Decision log" dans `CLAUDE.md` pour qu'il corresponde.
6. Afficher le contenu de l'ADR créé dans la réponse.
