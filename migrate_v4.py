#!/usr/bin/env python3
"""
Migration V4 of pp1_collection.db (PP1/Photomaton)
- Adds artworks.title / title_fr / title_nl / title_en (nullable: not every
  artwork has a title), requested by the frontend client for parity with
  description/keywords.
Usage: python migrate_v4.py <db_path>
"""
import sys
import sqlite3

DB = sys.argv[1] if len(sys.argv) > 1 else 'pp1_collection.db'


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    report = []

    def col_exists(table, col):
        return col in [r[1] for r in cur.execute(f'PRAGMA table_info({table})')]

    # ── artworks.title i18n ─────────────────────────────────────────────
    for c in ('title', 'title_fr', 'title_nl', 'title_en'):
        if not col_exists('artworks', c):
            cur.execute(f'ALTER TABLE artworks ADD COLUMN {c} TEXT')
            report.append(f'artworks.{c} added (NULL)')
        else:
            report.append(f'artworks.{c} already present')

    con.commit()
    con.close()
    print('\n'.join('  • ' + r for r in report))


if __name__ == '__main__':
    main()
