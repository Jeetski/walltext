# CLI Reference

Walltext can be driven entirely from the command line.

## Basic Usage

Apply text directly as wallpaper:
```powershell
walltext text "deploy completed successfully"
```

Render text to a PNG without applying it:
```powershell
walltext render .\out\status.png "build failed on staging"
```

Read text from a file and apply it immediately:
```powershell
walltext file .\status.txt
```

## Markdown Actions

Render or apply Markdown directly:
```powershell
walltext md validate .\today.md
walltext md render .\today.md --output .\out\today.png
walltext md apply .\today.md
```

## Dynamic Services

Watch a plain text file and reapply the wallpaper whenever the file changes:
```powershell
walltext watch .\status.txt
```

Apply the next configured item in rotation immediately:
```powershell
walltext run
walltext run --index 2
```

Run the JSON-configured scheduler:
```powershell
walltext listen --config .\quotes.json
```

Manage the background listener:
```powershell
walltext listener start
walltext listener status
walltext listener stop
```

Manage startup at login:
```powershell
walltext startup enable
walltext startup status
walltext startup disable
```

## Config Management

Manage the JSON config from the CLI:
```powershell
walltext config init
walltext config add "Stay focused."
walltext config add-file .\quotes\today.md
walltext config set-inline-md 1 "# New Title"
walltext config mode random
walltext config schedule daily --time 09:00
walltext config schedule interval 30
walltext config render set --size 40 --fg "#ffffff" --bg "#000000"
walltext config import-items .\quotes.txt --mode lines
walltext config list
```

## App Management
Open the GUI manager:
```powershell
walltext manager
```

Print combined config/listener/startup status:
```powershell
walltext status
walltext info
```
