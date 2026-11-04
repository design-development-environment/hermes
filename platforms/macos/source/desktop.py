#!/usr/bin/env python3
"""Hermes desktop controller with explicit X11 capability checks."""

import argparse
import re
import shutil
import mac_commands as subprocess
import sys
import time
from platform_support import graphical_environment, require_x11_automation


def require_tool(name):
    if name in {'wmctrl','xdotool'}:
        require_x11_automation()
    elif not shutil.which(name):
        raise RuntimeError('Executable is not installed: ' + name)


def run(args, capture=False):
    return subprocess.run(
        args, check=True, text=True, capture_output=capture,
        env=graphical_environment(),
    )


def get_windows():
    return subprocess.windows()


def find_unique_window(query, field):
    matches = [
        w for w in get_windows()
        if query.casefold() in w[field].casefold()
    ]

    if not matches:
        sys.exit(f"No window found matching {field}: {query}")

    if len(matches) > 1:
        print("Ambiguous match. Matching windows:", file=sys.stderr)
        for w in matches:
            print(
                f"  {w['id']}  {w['class']}  {w['title']}",
                file=sys.stderr,
            )
        sys.exit("Use a more specific title or application class.")

    return matches[0]


def focus_window(window):
    require_tool("xdotool")
    run(["wmctrl", "-ia", window["id"]])

    expected = int(window["id"], 16)

    for _ in range(30):
        active = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True,
        )

        if active.returncode == 0:
            try:
                if int(active.stdout.strip()) == expected:
                    return
            except ValueError:
                pass

        time.sleep(0.1)

    sys.exit(
        f"Focus verification failed for {window['title']}. "
        "No text was sent."
    )


def type_text(text):
    require_tool("xdotool")
    run(["xdotool", "type", "--clearmodifiers", "--", text])


def main():
    parser = argparse.ArgumentParser(description="Hermes desktop controller")
    sub = parser.add_subparsers(dest="action", required=True)

    launch = sub.add_parser("launch", help="Launch an application")
    launch.add_argument("application")
    launch.add_argument("args", nargs="*")

    sub.add_parser("windows", help="List open windows")

    focus = sub.add_parser("focus", help="Focus a window by title")
    focus.add_argument("title")

    focus_class = sub.add_parser(
        "focus-class", help="Focus a window by application class"
    )
    focus_class.add_argument("class_name")

    typing = sub.add_parser("type", help="Type into the focused window")
    typing.add_argument("text")

    targeted = sub.add_parser(
        "type-to", help="Focus a uniquely matched title, then type"
    )
    targeted.add_argument("title")
    targeted.add_argument("text")

    targeted_class = sub.add_parser(
        "type-to-class",
        help="Focus a uniquely matched application class, then type",
    )
    targeted_class.add_argument("class_name")
    targeted_class.add_argument("text")

    key = sub.add_parser("key", help="Send a keyboard shortcut")
    key.add_argument("shortcut")

    targeted_key = sub.add_parser(
        "key-to-class", help="Focus an application and send a shortcut"
    )
    targeted_key.add_argument("class_name")
    targeted_key.add_argument("shortcut")


    sub.add_parser(
        "mouse-position",
        help="Get mouse coordinates and screen dimensions",
    )

    mouse_move = sub.add_parser(
        "mouse-move",
        help="Move mouse to screen coordinates",
    )
    mouse_move.add_argument("x", type=int)
    mouse_move.add_argument("y", type=int)

    mouse_click = sub.add_parser(
        "mouse-click",
        help="Click at screen coordinates",
    )
    mouse_click.add_argument("x", type=int)
    mouse_click.add_argument("y", type=int)
    mouse_click.add_argument("button", type=int)
    mouse_click.add_argument("clicks", type=int)

    mouse_scroll = sub.add_parser(
        "mouse-scroll",
        help="Scroll at screen coordinates",
    )
    mouse_scroll.add_argument("x", type=int)
    mouse_scroll.add_argument("y", type=int)
    mouse_scroll.add_argument("direction", choices=["up", "down"])
    mouse_scroll.add_argument("steps", type=int)

    args = parser.parse_args()

    if args.action == "launch":
        if args.application not in subprocess.ALIASES and not shutil.which(args.application):
            sys.exit(f"Application executable not found: {args.application}")
        subprocess.Popen(
            [args.application, *args.args],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=graphical_environment(),
        )
        print(f"Launched: {args.application}")

    elif args.action == "windows":
        for w in get_windows():
            print(f"{w['id']}  {w['class']}  {w['title']}")

    elif args.action == "focus":
        w = find_unique_window(args.title, "title")
        focus_window(w)
        print(f"Focus verified: {w['title']}")

    elif args.action == "focus-class":
        w = find_unique_window(args.class_name, "class")
        focus_window(w)
        print(f"Focus verified: {w['class']} — {w['title']}")

    elif args.action == "type":
        type_text(args.text)
        print("Text sent to the focused window.")

    elif args.action == "type-to":
        w = find_unique_window(args.title, "title")
        focus_window(w)
        type_text(args.text)
        print(f"Typed into verified window: {w['title']}")

    elif args.action == "type-to-class":
        w = find_unique_window(args.class_name, "class")
        focus_window(w)
        type_text(args.text)
        print(f"Typed into verified window: {w['class']} — {w['title']}")

    elif args.action == "key-to-class":
        require_tool("xdotool")
        w = find_unique_window(args.class_name, "class")
        focus_window(w)
        run([
            "xdotool", "key", "--clearmodifiers", args.shortcut
        ])
        print(f"Shortcut sent to: {w['class']} — {w['title']}")


    elif args.action == "mouse-position":
        require_tool("xdotool")
        location = run(
            ["xdotool", "getmouselocation", "--shell"],
            capture=True,
        )
        geometry = run(
            ["xdotool", "getdisplaygeometry"],
            capture=True,
        )
        print(location.stdout.strip())
        print("SCREEN=" + geometry.stdout.strip())

    elif args.action in {"mouse-move", "mouse-click", "mouse-scroll"}:
        require_tool("xdotool")

        geometry = run(
            ["xdotool", "getdisplaygeometry"],
            capture=True,
        ).stdout.split()

        width, height = map(int, geometry[:2])

        if not (0 <= args.x < width and 0 <= args.y < height):
            sys.exit(
                f"Coordinates outside screen bounds: "
                f"0 <= x < {width}, 0 <= y < {height}"
            )

        run([
            "xdotool", "mousemove", "--sync",
            str(args.x), str(args.y),
        ])

        if args.action == "mouse-move":
            print(f"Mouse moved to ({args.x}, {args.y})")

        elif args.action == "mouse-click":
            if args.button not in (1, 3):
                sys.exit("Only left and right clicks are allowed.")

            if args.clicks not in (1, 2):
                sys.exit("Only single and double clicks are allowed.")

            for _ in range(args.clicks):
                run([
                    "xdotool", "click",
                    str(args.button),
                ])

            print(
                f"Clicked button {args.button} "
                f"{args.clicks} time(s) at ({args.x}, {args.y})"
            )

        elif args.action == "mouse-scroll":
            if not 1 <= args.steps <= 10:
                sys.exit("Scroll steps must be between 1 and 10.")

            button = "4" if args.direction == "up" else "5"

            run([
                "xdotool", "click",
                "--repeat", str(args.steps),
                "--delay", "80",
                button,
            ])

            print(
                f"Scrolled {args.direction} {args.steps} steps "
                f"at ({args.x}, {args.y})"
            )

    elif args.action == "key":
        require_tool("xdotool")
        if not re.fullmatch(r"[A-Za-z0-9_+.-]+", args.shortcut):
            sys.exit("Invalid shortcut format.")
        run(["xdotool", "key", "--clearmodifiers", args.shortcut])
        print(f"Shortcut sent: {args.shortcut}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(f"Action failed (exit {exc.returncode}).")
