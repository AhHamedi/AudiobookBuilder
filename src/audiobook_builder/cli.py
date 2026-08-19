"""Typer CLI with Rich output."""

from __future__ import annotations

import concurrent.futures as futures
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from audiobook_builder import __version__
from audiobook_builder.build import (
    build_m4b,
    default_title_from_files,
    guess_book_title_from_files,
    infer_series_name,
    sanitize_filename_base,
)
from audiobook_builder.discover import dedupe_exact_audio_files, discover_audio_files
from audiobook_builder.ffmpeg import (
    FFmpegError,
    check_ffmpeg,
    ffprobe_duration_seconds,
    normalize_aac_bitrate,
    select_aac_encoder,
)
from audiobook_builder.grouping import discover_subfolder_groups, group_by_leading_number

app = typer.Typer(
    name="audiobook-build",
    no_args_is_help=True,
    help="Build .m4b audiobooks for Apple Books from MP3 and other audio.",
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(__version__)
        raise typer.Exit()


def _banner() -> None:
    console.print(
        Panel.fit(
            f"[bold cyan]Audiobook builder[/bold cyan]  [dim]v{__version__}[/dim]\n"
            "[dim]AAC .m4b with chapters for macOS Books[/dim]",
            border_style="cyan",
        )
    )


def _report_duplicates(duplicates: list[tuple[Path, Path]]) -> None:
    for duplicate, original in duplicates:
        console.print(
            f"[yellow]Skipping duplicate[/yellow] {duplicate.name} "
            f"[dim](same content as {original.name})[/dim]"
        )


def _resolve_encoder_label(encoder: str, bitrate: str) -> tuple[str, str]:
    selected = select_aac_encoder(encoder)
    effective_bitrate = normalize_aac_bitrate(selected, bitrate)
    return selected, effective_bitrate


def _resolve_parallel_jobs(requested_jobs: int, total_books: int) -> int:
    """Compute batch parallelism. `0` means auto."""
    if total_books <= 0:
        return 1
    if requested_jobs > 0:
        return min(requested_jobs, total_books)

    cpu_count = os.cpu_count() or 1
    auto_jobs = max(1, min(6, cpu_count // 3))
    return min(auto_jobs, total_books)


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed version and exit.",
    ),
) -> None:
    """Audiobook builder for macOS Books."""


@app.command("build")
def cmd_build(
    directory: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Folder containing audio files for one audiobook.",
    ),
    title: Optional[str] = typer.Option(
        None,
        "--title",
        "-t",
        help="Audiobook title (default: from first filename).",
    ),
    author: str = typer.Option(
        ...,
        "--author",
        "-a",
        prompt=True,
        help="Author or narrator shown in Books.",
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        "-o",
        help="Output .m4b path (default: <directory>/<sanitized title>.m4b).",
    ),
    bitrate: str = typer.Option("96k", "--bitrate", help="AAC bitrate."),
    encoder: str = typer.Option(
        "auto",
        "--encoder",
        help="AAC encoder: auto, aac, or aac_at.",
    ),
    cover: Optional[Path] = typer.Option(
        None,
        "--cover",
        "-c",
        exists=True,
        dir_okay=False,
        help="Cover image (JPEG/PNG).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="List files only; no encode."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite without asking."),
) -> None:
    """Merge all audio in one folder into a single .m4b."""
    _banner()
    if not dry_run:
        try:
            check_ffmpeg()
        except FFmpegError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e

    files = discover_audio_files(directory)
    if not files:
        console.print(f"[red]No audio files found in {directory}[/red]")
        raise typer.Exit(1)
    files, duplicates = dedupe_exact_audio_files(files)
    _report_duplicates(duplicates)

    book_title = title or default_title_from_files(files)
    if out is None:
        out = directory / f"{sanitize_filename_base(book_title)}.m4b"
    else:
        out = Path(out)
        if out.suffix.lower() != ".m4b":
            out = out.with_suffix(".m4b")

    if out.exists() and not dry_run and not force:
        if not typer.confirm(f"Overwrite [cyan]{out}[/cyan]?"):
            raise typer.Exit(0)
    selected_encoder = "auto"
    effective_bitrate = bitrate
    if not dry_run:
        try:
            selected_encoder, effective_bitrate = _resolve_encoder_label(encoder, bitrate)
        except FFmpegError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e

    table = Table(title="Tracks", show_header=True, header_style="bold")
    table.add_column("#", style="dim", width=4)
    table.add_column("File")
    table.add_column("Duration", justify="right")
    total_sec = 0.0
    for i, p in enumerate(files, start=1):
        try:
            d = ffprobe_duration_seconds(p)
            total_sec += d
            m, s = divmod(int(round(d)), 60)
            h, m = divmod(m, 60)
            if h:
                dur = f"{h:d}:{m:02d}:{s:02d}"
            else:
                dur = f"{m:d}:{s:02d}"
        except FFmpegError as e:
            if dry_run:
                dur = "—"
            else:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(1) from e
        table.add_row(str(i), p.name, dur)
    console.print(table)
    console.print(
        f"[green]{len(files)}[/green] files  ·  [bold]{book_title}[/bold]  ·  "
        f"{total_sec / 3600:.2f} h"
    )
    if not dry_run:
        console.print(
            f"[dim]Encoder:[/dim] {selected_encoder}  [dim]Bitrate:[/dim] {effective_bitrate}"
        )

    if dry_run:
        console.print("[yellow]Dry run — no encode.[/yellow]")
        return

    console.print(f"[bold]Encoding[/bold] [cyan]{out.name}[/cyan] ...")
    try:
        build_m4b(
            files,
            out,
            title=book_title,
            author=author,
            bitrate=bitrate,
            cover=cover,
            dry_run=False,
            stream_output=True,
            encoder=encoder,
        )
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    console.print(Panel(f"[green]Done[/green]  {out}", border_style="green"))


def _natural_key_str(s: str) -> list:
    from audiobook_builder.discover import natural_sort_key

    return natural_sort_key(s)


def _batch_group_sort_key(key: str) -> tuple:
    """Sort batch groups: numbers, ``Volume N``, ``_other``, then names."""
    from audiobook_builder.discover import natural_sort_key

    if key == "_other":
        return (3, [])
    if key.startswith("v") and key[1:].isdigit():
        return (1, [int(key[1:])])
    if key.isdigit():
        return (1, [int(key)])
    return (0, natural_sort_key(key))


@app.command("batch")
def cmd_batch(
    root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Folder of audio (flat + group by leading number) or parent of book subfolders.",
    ),
    author: str = typer.Option(
        ...,
        "--author",
        "-a",
        prompt=True,
        help="Author or narrator for every output.",
    ),
    out_dir: Optional[Path] = typer.Option(
        None,
        "--out-dir",
        "-o",
        help="Output directory (default: parent of root).",
    ),
    one_subfolder_per_book: bool = typer.Option(
        False,
        "--one-subfolder-per-book",
        help="One audiobook per immediate child directory of root.",
    ),
    title_template: Optional[str] = typer.Option(
        None,
        "--title-template",
        help="Optional template; use {n} for group name / folder name.",
    ),
    bitrate: str = typer.Option("96k", "--bitrate", help="AAC bitrate."),
    encoder: str = typer.Option(
        "auto",
        "--encoder",
        help="AAC encoder: auto, aac, or aac_at.",
    ),
    cover: Optional[Path] = typer.Option(
        None,
        "--cover",
        exists=True,
        dir_okay=False,
        help="Cover image applied to every audiobook.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="List planned outputs only."),
    jobs: int = typer.Option(
        0,
        "--jobs",
        "-j",
        min=0,
        help="Parallel book encodes. 0 = auto.",
    ),
    skip_existing: bool = typer.Option(
        False,
        "--skip-existing",
        help="Skip outputs that already exist instead of prompting or overwriting.",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite without asking."),
) -> None:
    """Build multiple .m4b files (series / many books)."""
    _banner()
    if not dry_run:
        try:
            check_ffmpeg()
        except FFmpegError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e

    root = root.resolve()
    if out_dir is None:
        out_dir = root.parent
    else:
        out_dir = Path(out_dir).resolve()
    selected_encoder = "auto"
    effective_bitrate = bitrate
    if not dry_run:
        try:
            selected_encoder, effective_bitrate = _resolve_encoder_label(encoder, bitrate)
        except FFmpegError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e

    if one_subfolder_per_book:
        groups = discover_subfolder_groups(root)
        if not groups:
            console.print(f"[red]No subfolders with audio under {root}[/red]")
            raise typer.Exit(1)
    else:
        files = discover_audio_files(root)
        if not files:
            console.print(f"[red]No audio files in {root}[/red]")
            raise typer.Exit(1)
        groups = group_by_leading_number(files)
        series_name = infer_series_name(files)
    if one_subfolder_per_book:
        series_name = None

    # Order groups: numbered books, Volume-N groups, then names/subfolders, then _other
    keys = [k for k in groups if k != "_other"]
    keys.sort(key=_batch_group_sort_key)
    if "_other" in groups:
        keys.append("_other")

    planned: list[tuple[str, list[Path], Path, str]] = []
    for key in keys:
        gfiles, duplicates = dedupe_exact_audio_files(groups[key])
        _report_duplicates(duplicates)
        if not gfiles:
            continue
        if title_template:
            book_title = title_template.format(n=key)
        else:
            book_title = guess_book_title_from_files(gfiles, series_name=series_name)
        safe_name = sanitize_filename_base(book_title)
        if not safe_name:
            safe_name = f"book_{key}"
        out_path = out_dir / f"{safe_name}.m4b"
        planned.append((key, gfiles, out_path, book_title))

    table = Table(title="Batch plan", show_header=True, header_style="bold")
    table.add_column("Group")
    table.add_column("Tracks", justify="right")
    table.add_column("Title")
    table.add_column("Output")
    for key, gfiles, out_path, book_title in planned:
        table.add_row(key, str(len(gfiles)), book_title, str(out_path.name))
    console.print(table)
    if not dry_run:
        console.print(
            f"[dim]Encoder:[/dim] {selected_encoder}  [dim]Bitrate:[/dim] {effective_bitrate}"
        )
        console.print(f"[dim]Parallel jobs:[/dim] {_resolve_parallel_jobs(jobs, len(planned))}")

    if dry_run:
        console.print("[yellow]Dry run — no encode.[/yellow]")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    runnable: list[tuple[str, list[Path], Path, str]] = []
    for key, gfiles, out_path, book_title in planned:
        if out_path.exists() and skip_existing:
            console.print(f"[dim]Keeping existing {out_path.name}[/dim]")
            continue
        if out_path.exists() and not force:
            if not typer.confirm(f"Overwrite [cyan]{out_path.name}[/cyan]?"):
                console.print(f"[dim]Skipped {out_path.name}[/dim]")
                continue
        runnable.append((key, gfiles, out_path, book_title))

    job_count = _resolve_parallel_jobs(jobs, len(runnable))
    if job_count == 1:
        for _key, gfiles, out_path, book_title in runnable:
            console.print(f"\n[bold]→[/bold] [cyan]{book_title}[/cyan] ({len(gfiles)} files)")
            console.print(f"  [dim]Encoding to {out_path.name}[/dim]")
            try:
                build_m4b(
                    gfiles,
                    out_path,
                    title=book_title,
                    author=author,
                    bitrate=bitrate,
                    cover=cover,
                    dry_run=False,
                    stream_output=True,
                    encoder=encoder,
                )
            except Exception as e:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(1) from e
            console.print(f"  [green]✓[/green] {out_path}")
    else:
        console.print(
            f"[bold]Starting parallel batch[/bold] with {job_count} workers "
            f"for {len(runnable)} books."
        )
        for _, gfiles, out_path, book_title in runnable:
            console.print(
                f"[dim]Queued {book_title} -> {out_path.name} ({len(gfiles)} files)[/dim]"
            )

        def _encode_one(item: tuple[str, list[Path], Path, str]) -> tuple[Path, str]:
            _, gfiles, out_path, book_title = item
            build_m4b(
                gfiles,
                out_path,
                title=book_title,
                author=author,
                bitrate=bitrate,
                cover=cover,
                dry_run=False,
                stream_output=False,
                encoder=encoder,
            )
            return out_path, book_title

        failures: list[str] = []
        completed = 0
        with futures.ThreadPoolExecutor(max_workers=job_count) as executor:
            future_map = {executor.submit(_encode_one, item): item for item in runnable}
            for future in futures.as_completed(future_map):
                _, _, out_path, book_title = future_map[future]
                try:
                    finished_out, finished_title = future.result()
                    completed += 1
                    console.print(
                        f"[green]✓[/green] ({completed}/{len(runnable)}) "
                        f"{finished_title} -> {finished_out.name}"
                    )
                except Exception as e:
                    failures.append(f"{book_title}: {e}")
                    console.print(f"[red]Failed[/red] {book_title}: {e}")

        if failures:
            raise typer.Exit(1)

    console.print(Panel(f"[green]Batch complete[/green]  → {out_dir}", border_style="green"))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
