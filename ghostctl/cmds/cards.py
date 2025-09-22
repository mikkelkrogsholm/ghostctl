"""Ghost cards command - generate and reference Ghost card HTML structures."""

import json
from typing import Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from ..exceptions import GhostCtlError

# Initialize CLI app
cli = typer.Typer(
    name="cards",
    help="Generate and reference Ghost card HTML structures",
    no_args_is_help=True,
)

console = Console()

# Card templates
CARD_TEMPLATES = {
    "callout": {
        "blue": {
            "template": '<div class="kg-card kg-callout-card kg-callout-card-blue">\n  <div class="kg-callout-emoji">{emoji}</div>\n  <div class="kg-callout-text">{text}</div>\n</div>',
            "default_emoji": "ℹ️",
            "description": "Info callout"
        },
        "green": {
            "template": '<div class="kg-card kg-callout-card kg-callout-card-green">\n  <div class="kg-callout-emoji">{emoji}</div>\n  <div class="kg-callout-text">{text}</div>\n</div>',
            "default_emoji": "✅",
            "description": "Success callout"
        },
        "yellow": {
            "template": '<div class="kg-card kg-callout-card kg-callout-card-yellow">\n  <div class="kg-callout-emoji">{emoji}</div>\n  <div class="kg-callout-text">{text}</div>\n</div>',
            "default_emoji": "⚠️",
            "description": "Warning callout"
        },
        "red": {
            "template": '<div class="kg-card kg-callout-card kg-callout-card-red">\n  <div class="kg-callout-emoji">{emoji}</div>\n  <div class="kg-callout-text">{text}</div>\n</div>',
            "default_emoji": "🚨",
            "description": "Alert callout"
        },
        "pink": {
            "template": '<div class="kg-card kg-callout-card kg-callout-card-pink">\n  <div class="kg-callout-emoji">{emoji}</div>\n  <div class="kg-callout-text">{text}</div>\n</div>',
            "default_emoji": "💡",
            "description": "Tip callout"
        }
    },
    "toggle": {
        "template": '''<div class="kg-card kg-toggle-card" data-kg-toggle-state="close">
  <div class="kg-toggle-heading">
    <h4 class="kg-toggle-heading-text">{heading}</h4>
    <button class="kg-toggle-card-icon">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <path d="M23.25,7.311,12.53,18.03a.749.749,0,0,1-1.06,0L.75,7.311"/>
      </svg>
    </button>
  </div>
  <div class="kg-toggle-content">{content}</div>
</div>'''
    },
    "button": {
        "template": '<div class="kg-card kg-button-card kg-align-{align}">\n  <a href="{url}" class="kg-btn kg-btn-accent">{text}</a>\n</div>'
    },
    "bookmark": {
        "template": '''<figure class="kg-card kg-bookmark-card">
  <a href="{url}" class="kg-bookmark-container">
    <div class="kg-bookmark-content">
      <div class="kg-bookmark-title">{title}</div>
      <div class="kg-bookmark-description">{description}</div>
      <div class="kg-bookmark-metadata">
        <span class="kg-bookmark-publisher">{publisher}</span>
      </div>
    </div>
  </a>
</figure>'''
    },
    "gallery": {
        "template": '''<figure class="kg-card kg-gallery-card kg-width-wide">
  <div class="kg-gallery-container">
    <div class="kg-gallery-row">
{images}
    </div>
  </div>
  <figcaption>{caption}</figcaption>
</figure>''',
        "image_template": '      <div class="kg-gallery-image">\n        <img src="{src}" width="{width}" height="{height}" alt="{alt}">\n      </div>'
    },
    "product": {
        "template": '''<div class="kg-card kg-product-card">
  <div class="kg-product-card-container">
    <img src="{image}" class="kg-product-card-image" alt="{title}">
    <div class="kg-product-card-content">
      <h4 class="kg-product-card-title">{title}</h4>
      <div class="kg-product-card-description">{description}</div>
      <div class="kg-product-card-rating">{rating}</div>
      <a href="{url}" class="kg-product-card-button">{button_text}</a>
    </div>
  </div>
</div>'''
    },
    "html": {
        "template": '<div class="kg-card kg-html-card">\n{content}\n</div>'
    },
    "code": {
        "template": '<pre class="kg-card kg-code-card language-{language}"><code>{code}</code></pre>'
    }
}


@cli.command("list")
def list_cards() -> None:
    """List all available Ghost card types with descriptions."""
    table = Table(title="Available Ghost Card Types", show_header=True)
    table.add_column("Card Type", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Usage", style="green")

    table.add_row(
        "callout",
        "Highlighted info boxes with emoji",
        "ghostctl cards generate callout --color blue --text 'Info'"
    )
    table.add_row(
        "toggle",
        "Collapsible FAQ sections",
        "ghostctl cards generate toggle --heading 'Q?' --content 'A'"
    )
    table.add_row(
        "button",
        "Call-to-action buttons",
        "ghostctl cards generate button --url '/link' --text 'Click'"
    )
    table.add_row(
        "bookmark",
        "Rich link previews",
        "ghostctl cards generate bookmark --url 'https://...'"
    )
    table.add_row(
        "gallery",
        "Image galleries",
        "ghostctl cards generate gallery --images img1.jpg,img2.jpg"
    )
    table.add_row(
        "product",
        "Product showcases",
        "ghostctl cards generate product --title 'Item' --price '$99'"
    )
    table.add_row(
        "html",
        "Custom HTML content",
        "ghostctl cards generate html --content '<div>...</div>'"
    )
    table.add_row(
        "code",
        "Code blocks with syntax highlighting",
        "ghostctl cards generate code --language python --code '...'"
    )

    console.print(table)


@cli.command("generate")
def generate_card(
    card_type: str = typer.Argument(..., help="Type of card to generate"),
    color: Optional[str] = typer.Option(None, help="Callout color (blue/green/yellow/red/pink)"),
    emoji: Optional[str] = typer.Option(None, help="Callout emoji"),
    text: Optional[str] = typer.Option(None, help="Card text content"),
    heading: Optional[str] = typer.Option(None, help="Toggle/section heading"),
    content: Optional[str] = typer.Option(None, help="Content for toggle/html cards"),
    url: Optional[str] = typer.Option(None, help="URL for button/bookmark/product cards"),
    title: Optional[str] = typer.Option(None, help="Title for bookmark/product cards"),
    description: Optional[str] = typer.Option(None, help="Description for bookmark/product cards"),
    publisher: Optional[str] = typer.Option(None, help="Publisher for bookmark card"),
    align: str = typer.Option("center", help="Button alignment (left/center/right)"),
    images: Optional[str] = typer.Option(None, help="Comma-separated image URLs for gallery"),
    caption: Optional[str] = typer.Option(None, help="Gallery caption"),
    image: Optional[str] = typer.Option(None, help="Product image URL"),
    rating: Optional[str] = typer.Option("⭐⭐⭐⭐⭐", help="Product rating"),
    button_text: Optional[str] = typer.Option("Buy Now", help="Product button text"),
    language: Optional[str] = typer.Option("javascript", help="Code language"),
    code: Optional[str] = typer.Option(None, help="Code content"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save to file"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy to clipboard"),
) -> None:
    """Generate HTML for a specific Ghost card type.

    Examples:
        # Generate a blue info callout
        ghostctl cards generate callout --color blue --text "Important info"

        # Generate a toggle/FAQ card
        ghostctl cards generate toggle --heading "Question?" --content "Answer here"

        # Generate a button
        ghostctl cards generate button --url "/signup" --text "Sign Up Now"

        # Generate and save to file
        ghostctl cards generate callout --color green --text "Success!" -o success.html
    """
    html = ""

    if card_type == "callout":
        if not color:
            color = "blue"
        if color not in CARD_TEMPLATES["callout"]:
            console.print(f"[red]Invalid color: {color}. Choose from: blue, green, yellow, red, pink[/red]")
            raise typer.Exit(1)

        template_data = CARD_TEMPLATES["callout"][color]
        emoji = emoji or template_data["default_emoji"]
        text = text or "Your text here"
        html = template_data["template"].format(emoji=emoji, text=text)

    elif card_type == "toggle":
        heading = heading or "Click to expand"
        content = content or "Hidden content here"
        html = CARD_TEMPLATES["toggle"]["template"].format(heading=heading, content=content)

    elif card_type == "button":
        url = url or "#"
        text = text or "Button Text"
        html = CARD_TEMPLATES["button"]["template"].format(url=url, text=text, align=align)

    elif card_type == "bookmark":
        url = url or "https://example.com"
        title = title or "Page Title"
        description = description or "Page description"
        publisher = publisher or "example.com"
        html = CARD_TEMPLATES["bookmark"]["template"].format(
            url=url, title=title, description=description, publisher=publisher
        )

    elif card_type == "gallery":
        if not images:
            console.print("[red]Gallery requires --images parameter with comma-separated URLs[/red]")
            raise typer.Exit(1)

        image_list = images.split(",")
        image_html = []
        for img in image_list:
            img = img.strip()
            image_html.append(
                CARD_TEMPLATES["gallery"]["image_template"].format(
                    src=img, width="800", height="600", alt="Gallery image"
                )
            )

        html = CARD_TEMPLATES["gallery"]["template"].format(
            images="\n".join(image_html),
            caption=caption or ""
        )

    elif card_type == "product":
        html = CARD_TEMPLATES["product"]["template"].format(
            image=image or "https://via.placeholder.com/400x300",
            title=title or "Product Name",
            description=description or "Product description",
            rating=rating,
            url=url or "#",
            button_text=button_text
        )

    elif card_type == "html":
        content = content or "<div>Your custom HTML here</div>"
        html = CARD_TEMPLATES["html"]["template"].format(content=content)

    elif card_type == "code":
        code = code or "// Your code here"
        html = CARD_TEMPLATES["code"]["template"].format(language=language, code=code)

    else:
        console.print(f"[red]Unknown card type: {card_type}[/red]")
        console.print("Use 'ghostctl cards list' to see available card types")
        raise typer.Exit(1)

    # Output the HTML
    if output:
        output.write_text(html)
        console.print(f"[green]✓ Card HTML saved to {output}[/green]")

    if copy:
        try:
            import pyperclip
            pyperclip.copy(html)
            console.print("[green]✓ Card HTML copied to clipboard[/green]")
        except ImportError:
            console.print("[yellow]Install 'pyperclip' to enable clipboard support[/yellow]")

    # Always show the generated HTML
    syntax = Syntax(html, "html", theme="monokai", line_numbers=False)
    console.print("\n[bold]Generated HTML:[/bold]")
    console.print(syntax)


@cli.command("reference")
def show_reference(
    card_type: Optional[str] = typer.Argument(None, help="Show reference for specific card type"),
) -> None:
    """Show HTML structure reference for Ghost cards.

    Examples:
        # Show reference for all cards
        ghostctl cards reference

        # Show reference for specific card
        ghostctl cards reference callout
    """
    if card_type:
        if card_type == "callout":
            console.print("[bold cyan]Callout Card Reference[/bold cyan]\n")
            for color, data in CARD_TEMPLATES["callout"].items():
                console.print(f"[bold]{color.capitalize()} ({data['description']}):[/bold]")
                syntax = Syntax(
                    data["template"].format(
                        emoji=data["default_emoji"],
                        text=f"{data['description']} text here"
                    ),
                    "html",
                    theme="monokai",
                    line_numbers=False
                )
                console.print(syntax)
                console.print()

        elif card_type in CARD_TEMPLATES:
            console.print(f"[bold cyan]{card_type.capitalize()} Card Reference[/bold cyan]\n")
            template = CARD_TEMPLATES[card_type].get("template", "")

            # Show example with placeholders
            example = template
            if card_type == "toggle":
                example = template.format(heading="Question?", content="Answer")
            elif card_type == "button":
                example = template.format(url="/link", text="Click Me", align="center")
            # ... etc for other types

            syntax = Syntax(example, "html", theme="monokai", line_numbers=False)
            console.print(syntax)

        else:
            console.print(f"[red]Unknown card type: {card_type}[/red]")
            raise typer.Exit(1)

    else:
        # Show overview of all cards
        console.print("[bold cyan]Ghost Cards HTML Reference[/bold cyan]\n")
        console.print("Use 'ghostctl cards reference <type>' for detailed examples")
        console.print("\nAvailable card types:")
        for card in ["callout", "toggle", "button", "bookmark", "gallery", "product", "html", "code"]:
            console.print(f"  • {card}")


@cli.command("create-post")
def create_post_with_cards(
    title: str = typer.Option(..., help="Post title"),
    template: str = typer.Option("faq", help="Template type: faq, product, tutorial"),
    output: Path = typer.Option(..., "--output", "-o", help="Output HTML file"),
) -> None:
    """Create a full post template with Ghost cards.

    Examples:
        # Create an FAQ post
        ghostctl cards create-post --title "FAQs" --template faq -o faq.html

        # Create a product showcase
        ghostctl cards create-post --title "Our Products" --template product -o products.html
    """
    templates = {
        "faq": '''<h1>{title}</h1>
<p>Find answers to commonly asked questions below.</p>

<div class="kg-card kg-toggle-card" data-kg-toggle-state="close">
  <div class="kg-toggle-heading">
    <h4 class="kg-toggle-heading-text">What is your refund policy?</h4>
    <button class="kg-toggle-card-icon">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <path d="M23.25,7.311,12.53,18.03a.749.749,0,0,1-1.06,0L.75,7.311"/>
      </svg>
    </button>
  </div>
  <div class="kg-toggle-content">We offer a 30-day money-back guarantee.</div>
</div>

<div class="kg-card kg-toggle-card" data-kg-toggle-state="close">
  <div class="kg-toggle-heading">
    <h4 class="kg-toggle-heading-text">Do you offer support?</h4>
    <button class="kg-toggle-card-icon">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <path d="M23.25,7.311,12.53,18.03a.749.749,0,0,1-1.06,0L.75,7.311"/>
      </svg>
    </button>
  </div>
  <div class="kg-toggle-content">Yes, we provide 24/7 support via email and chat.</div>
</div>''',

        "product": '''<h1>{title}</h1>
<p>Check out our featured products below.</p>

<div class="kg-card kg-product-card">
  <div class="kg-product-card-container">
    <img src="https://via.placeholder.com/400x300" class="kg-product-card-image" alt="Product">
    <div class="kg-product-card-content">
      <h4 class="kg-product-card-title">Premium Package</h4>
      <div class="kg-product-card-description">Everything you need to get started.</div>
      <div class="kg-product-card-rating">⭐⭐⭐⭐⭐</div>
      <a href="#" class="kg-product-card-button">$99 - Buy Now</a>
    </div>
  </div>
</div>

<div class="kg-card kg-callout-card kg-callout-card-green">
  <div class="kg-callout-emoji">🎉</div>
  <div class="kg-callout-text"><strong>Limited Time:</strong> Get 20% off with code SAVE20</div>
</div>''',

        "tutorial": '''<h1>{title}</h1>

<div class="kg-card kg-callout-card kg-callout-card-blue">
  <div class="kg-callout-emoji">ℹ️</div>
  <div class="kg-callout-text">This tutorial will guide you through the process step by step.</div>
</div>

<h2>Step 1: Getting Started</h2>
<p>First, let's set up the basics...</p>

<div class="kg-card kg-callout-card kg-callout-card-yellow">
  <div class="kg-callout-emoji">⚠️</div>
  <div class="kg-callout-text"><strong>Important:</strong> Make sure you have completed the prerequisites.</div>
</div>

<h2>Step 2: Implementation</h2>
<p>Now let's implement the solution...</p>

<pre class="kg-card kg-code-card language-javascript"><code>// Example code
function example() {{
  console.log("Hello World");
}}</code></pre>

<div class="kg-card kg-callout-card kg-callout-card-green">
  <div class="kg-callout-emoji">✅</div>
  <div class="kg-callout-text">Congratulations! You've completed the tutorial.</div>
</div>

<div class="kg-card kg-button-card kg-align-center">
  <a href="/next-steps" class="kg-btn kg-btn-accent">Continue to Next Steps →</a>
</div>'''
    }

    if template not in templates:
        console.print(f"[red]Unknown template: {template}. Choose from: faq, product, tutorial[/red]")
        raise typer.Exit(1)

    html = templates[template].format(title=title)
    output.write_text(html)
    console.print(f"[green]✓ Post template saved to {output}[/green]")
    console.print(f"\nTo create the post, run:")
    console.print(f"[cyan]ghostctl posts create --title '{title}' --file {output} --status draft[/cyan]")


# Register commands
def register_commands(app: typer.Typer) -> None:
    """Register cards commands with the main app."""
    app.add_typer(cli)