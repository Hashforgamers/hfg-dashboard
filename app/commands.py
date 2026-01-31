# app/commands.py
import click
from flask.cli import with_appcontext
from app.services.rawg_sync_service import RAWGSyncService


@click.command('sync-rawg-games')
@click.option('--pages', default=10, help='Number of pages (40 games per page)')
@click.option('--update/--no-update', default=True, help='Update existing games')
@with_appcontext
def sync_rawg_games_command(pages, update):
    """Sync games from RAWG API with images!"""
    click.echo(f"🚀 Syncing {pages} pages from RAWG ({pages * 40} games with images)...")
    
    result = RAWGSyncService.sync_games(max_pages=pages, update_existing=update)
    
    click.echo(f"""
    ✅ Complete!
    - Added: {result['added']} (with images!)
    - Updated: {result['updated']}
    - Errors: {result['errors']}
    """)


def register_commands(app):
    app.cli.add_command(sync_rawg_games_command)
