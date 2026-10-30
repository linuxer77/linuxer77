# the battle

The top of the profile README looks like plain text. It isn't. `battle-light.svg` and
`battle-dark.svg` are 18-second animated SVGs (pure SMIL, no JavaScript) that GitHub renders
as-is: Charizard and Blastoise walk onto the page and fight, while Gengar eats, spits out and
steals bits of the text above them. `make_battle.py` generates both;
edit `H1_TEXT` / `PARAS` near the top to change the copy, or the beat sheet below them to
change the fight, then:

```
pip install pillow
python3 make_battle.py
```

## Sprite credits

Sprites from [PMD Sprite Collab](https://sprites.pmdcollab.org) (CC BY-NC 4.0), in `sprites/`:

- Charizard (#0006): CHUNSOFT, Emboarger
- Blastoise (#0009): CHUNSOFT
- Gengar (#0094): CHUNSOFT, Emboarger

Pokémon © Nintendo / Creatures Inc. / GAME FREAK inc. Fan project, not affiliated.
