"""Render the supplied SVG wordmarks for the native installer."""
from pathlib import Path
import cairosvg

destination = Path(__file__).resolve().parent
for theme in ('Dark', 'Light'):
    cairosvg.svg2png(url=str(destination / 'branding' / f'hermes-{theme.lower()}.svg'),
                    write_to=str(destination / f'logo-{theme.lower()}.png'), output_width=230)
