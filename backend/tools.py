"""
All Ame AI tools in Groq function-calling JSON Schema format.
tools_list is imported by main.py and passed to the Groq API.
"""

tools_list = [
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": (
                "Open ANY application, program, shortcut, or virtual machine on the user's Windows PC. "
                "This searches the entire system: Start Menu, Desktop shortcuts, Program Files, Registry, "
                "and VirtualBox VMs. Use this for EVERYTHING — apps, games, VMs, tools, utilities. "
                "Examples: 'Spotify', 'Kali Linux', 'Chrome', 'OBS', 'Premiere Pro'. "
                "ALWAYS use this instead of run_terminal_command when the goal is to open/start/launch something. "
                "ALWAYS call this tool immediately instead of saying you will open it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "The common name of the application to open (e.g. 'chrome', 'spotify', 'discord')."}
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": (
                "Create a file on the user's PC at the given path with the given content. "
                "Use 'desktop' as the path prefix to save to the Desktop. "
                "Always call this when the user asks to create or write a file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": (
                            "Full path where the file should be created. "
                            "Use 'desktop/filename.ext' for the user's Desktop, "
                            "'downloads/filename.ext' for Downloads, etc."
                        ),
                    },
                    "content": {
                        "type": "string",
                        "description": "The text content to write into the file.",
                    },
                },
                "required": ["filepath"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_application",
            "description": "Close/kill a running desktop application by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "The common name of the application to close (e.g. 'chrome', 'spotify')."}
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Set the system master volume to a specific level between 0 and 100.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "Volume level from 0 (silent) to 100 (maximum).", "minimum": 0, "maximum": 100}
                },
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mute_volume",
            "description": "Mute the system audio/volume.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unmute_volume",
            "description": "Unmute the system audio/volume.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Capture a screenshot of the entire screen and save it to the Desktop.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lock_screen",
            "description": "Lock the Windows screen / workstation.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current local time in HH:MM AM/PM format.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_date",
            "description": "Get the current local date in a human-readable format (e.g. Monday, January 1, 2025).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Search for files on the Desktop and in Documents that match the given query string. "
                "IMPORTANT: The query MUST be a specific filename or meaningful partial filename (e.g. 'resume', 'project_notes'). "
                "NEVER pass wildcard characters like '*', '?', or '**'. "
                "NEVER pass a bare file extension like '.py', '.txt', or '.mp4' without a specific name prefix — "
                "this will match thousands of files and hang the system. "
            "The search is fuzzy and checks full paths, so passing 'untitled project in test folder' will intelligently match. "
                "If the user has not named a specific file, ask them for the filename before calling this tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Specific filename or meaningful partial filename to search for. No wildcards, no bare extensions."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type or paste a given text string into the currently focused input field or application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to type into the active window."}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "copy_to_clipboard",
            "description": "Copy a given text string to the system clipboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to copy to the clipboard."}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_song_on_spotify",
            "description": "Search for a specific song or artist on Spotify and immediately start playing it. Use this when the user wants to play a named track or artist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The song title, artist name, or both to search for on Spotify (e.g. 'Blinding Lights The Weeknd')."},
                    "device": {"type": "string", "description": "Optional device to play on: 'phone', 'tv', 'computer', or a specific device name. Defaults to computer/PC if not specified."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_spotify_by_mood",
            "description": "Play a Spotify playlist that matches a given mood, genre, or activity (e.g. 'chill', 'workout', 'lo-fi', 'jazz', 'happy', 'focus').",
            "parameters": {
                "type": "object",
                "properties": {
                    "mood_or_genre": {"type": "string", "description": "A mood, genre, or activity keyword to find a matching playlist (e.g. 'chill', 'rap', 'study')."},
                    "device": {"type": "string", "description": "Optional device to play on: 'phone', 'tv', 'computer', or a specific device name. Defaults to computer/PC if not specified."}
                },
                "required": ["mood_or_genre"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_music_on_youtube",
            "description": "Search YouTube for a song or video and automatically play the first result in a browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for the YouTube music video or song (e.g. 'Bohemian Rhapsody Queen')."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_music_on_spotify",
            "description": "Open the Spotify desktop application so the user can browse and play music manually.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pause_music",
            "description": "Pause or resume the currently playing music/media using the system media play/pause key.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pause_spotify",
            "description": "Pause the currently playing Spotify track.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resume_spotify",
            "description": "Resume the paused Spotify track.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "next_track",
            "description": "Skip to the next track in the currently playing media application.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "previous_track",
            "description": "Go back to the previous track in the currently playing media application.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search_ddg",
            "description": "Search the web using DuckDuckGo and return a concise text summary. Use ONLY for real-time data you cannot know from training (breaking news, live prices, current weather, today's sports scores). NEVER use this for general knowledge questions about cities, countries, history, science, people, or geography — answer those from your own knowledge. Returns text only, does not open a browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query (e.g. 'latest AI news 2025', 'weather in Tokyo')."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": (
                "Open any website or URL in the default browser. "
                "Use this whenever the user asks to: open a website by name (e.g. 'open Amazon', "
                "'go to Netflix', 'open YouTube', 'open Reddit'), visit a specific URL, "
                "search on a specific site, or browse to any web address. "
                "For well-known sites, construct the URL yourself (e.g. Amazon → https://www.amazon.com, "
                "Netflix → https://www.netflix.com). "
                "For Amazon searches, use https://www.amazon.com/s?k=QUERY. "
                "ALWAYS call this tool instead of just saying you will open something."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full URL to open (e.g. 'https://www.amazon.com/s?k=rtx+3050')."}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "google_search",
            "description": (
                "Open Google in the browser with a search query. "
                "ONLY use when the user EXPLICITLY says 'Google X', 'search Google for X', or 'look it up'. "
                "NEVER use this to answer general knowledge questions — answer those from your own knowledge. "
                "If the user asks about a city, country, person, or topic, just answer — do NOT open Google."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query to look up on Google."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_travel",
            "description": (
                "Search for travel options (trains, buses, flights) between two places. "
                "Works globally — any country, any language, any route. "
                "Use for any request involving journeys: trains, tickets, getting from A to B, travel times, prices. "
                "Converts relative dates ('next Friday', 'vendredi prochain', 'nächsten Freitag') to YYYY-MM-DD before calling. "
                "All parameters are optional — pass only what the user mentioned. "
                "ALWAYS call immediately — never say you will search without calling this tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin":      {"type": "string", "description": "Departure city or station (any language)"},
                    "destination": {"type": "string", "description": "Arrival city or station (any language)"},
                    "date":        {"type": "string", "description": "Departure date in YYYY-MM-DD format"},
                    "time":        {"type": "string", "description": "Departure time in HH:MM (24h) format"},
                    "mode":        {"type": "string", "description": "Transport mode: 'train', 'bus', 'flight', etc. Default: train"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_google_maps",
            "description": "Open Google Maps in the browser and search for a location or directions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "The place, address, or location name to look up on Google Maps."}
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_youtube",
            "description": "Open YouTube in the browser and search for videos matching the given query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search term to look up on YouTube."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scrape_and_summarize",
            "description": "Fetch the content of a web page at the given URL and return its readable text content. Useful for reading articles, documentation, or any web page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full URL of the web page to fetch and extract content from."}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_web_task",
            "description": "Run an autonomous multi-step web browsing task using an AI agent. Use this for complex tasks like filling out forms, extracting structured data, logging in, navigating multi-page sites, or any web task that requires several interactions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "A plain-English description of what the agent should accomplish on the web."},
                    "starting_url": {"type": "string", "description": "Optional URL to begin the task at. If omitted, the agent will determine the best starting point."}
                },
                "required": ["task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save an important personal fact about the user to long-term memory. Call silently whenever the user reveals: name, age, city, job, preferences (including favorite music, artists, and Spotify playlists), hobbies, relationships, ongoing projects, or future plans. Do NOT announce you are saving — just save and continue naturally.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Memory category: identity, preferences, projects, relationships, wishes, or notes."},
                    "key": {"type": "string", "description": "Short key describing what this fact is (e.g. 'name', 'job', 'favorite_music')."},
                    "value": {"type": "string", "description": "The value to remember (e.g. 'Ahmed', 'software engineer', 'lo-fi hip hop')."}
                },
                "required": ["category", "key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_screen",
            "description": "Capture the current screen and analyze it with AI vision. Use when the user asks: 'what's on my screen?', 'help me with this', or 'look at this'. If you already proactively warned the user and have the technical details in your photographic memory, DO NOT call this tool. Only call this when you need a fresh look.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "What to look for or analyze on the screen (e.g. 'Describe everything visible', 'Read the text')."}
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_webcam",
            "description": "Capture a frame from the webcam and analyze it with AI vision. Use when the user asks: 'look at me', 'what do you see?', 'describe what's in front of me', or any camera/webcam request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "What to look for or analyze in the webcam frame (e.g. 'Describe what you see', 'What am I wearing?')."}
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_terminal_command",
            "description": "Run a Windows command or describe a task in plain English and let AI generate the right command. Use for: running scripts, checking system info, file operations via CMD, or any shell task. Safety: destructive commands are blocked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The exact command to run, OR leave empty if providing task_description."},
                    "task_description": {"type": "string", "description": "Plain English description of what to do (AI will generate the command). Use this when you don't know the exact command."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "organize_desktop",
            "description": "Organize desktop files by grouping them into subfolders by type (Images, Documents, Videos, etc.) or by date. Use when user asks to 'clean up' or 'organize' their desktop.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "description": "How to organize: 'type' (by file type) or 'date' (by date modified)."}
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clean_desktop",
            "description": "Move all files on the desktop into a single archive folder named 'Desktop Archive YYYY-MM-DD'. Use when the user wants to quickly clear everything off the desktop.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_desktop",
            "description": "List all files and folders on the desktop with their sizes.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_folder",
            "description": (
                "Open a folder by name in Windows Explorer. "
                "Use when the user says 'open my X folder', 'open the folder called X', 'show me the X folder'. "
                "Searches Desktop, Documents, Downloads, and home directory with fuzzy matching — "
                "pass the folder name EXACTLY as the user said it, do not correct or alter spelling. "
                "The search handles case, spaces, and partial matches automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_name": {"type": "string", "description": "The name of the folder to open (e.g. 'Ame', 'Projects', 'Photos')."}
                },
                "required": ["folder_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_mouse",
            "description": "Move the mouse cursor to an absolute screen position.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate in pixels."},
                    "y": {"type": "integer", "description": "Y coordinate in pixels."}
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_mouse",
            "description": "Click the mouse at an optional position. If x and y are omitted, clicks at current position.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate to click (optional)."},
                    "y": {"type": "integer", "description": "Y coordinate to click (optional)."},
                    "button": {"type": "string", "description": "Mouse button: 'left', 'right', or 'middle'. Default: 'left'."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "double_click",
            "description": "Double-click the mouse at an optional position.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate (optional)."},
                    "y": {"type": "integer", "description": "Y coordinate (optional)."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Press a keyboard key (e.g. 'enter', 'tab', 'escape', 'f5').",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The key to press (e.g. 'enter', 'tab', 'space', 'f5')."}
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hotkey",
            "description": "Press a keyboard hotkey combination (e.g. ctrl+c, alt+tab, win+d).",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "array", "items": {"type": "string"}, "description": "List of keys to press together (e.g. ['ctrl', 'c'])."}
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text_slow",
            "description": "Type text character by character with a small delay. Better for apps that don't accept paste.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to type."}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot_and_analyze",
            "description": "Take a screenshot of the current screen and return it for analysis. Use this to see what's currently on screen before clicking or interacting.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "launch_steam_game",
            "description": "Launch a Steam game by name using the Steam URI protocol. Works even if Steam is closed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "game_name": {"type": "string", "description": "Name of the game to launch (e.g. 'PUBG', 'CS2', 'Dota 2')."}
                },
                "required": ["game_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_steam_game",
            "description": "Open the Steam install dialog to download/install a game.",
            "parameters": {
                "type": "object",
                "properties": {
                    "game_name": {"type": "string", "description": "Name of the game to install (e.g. 'PUBG', 'Rust')."}
                },
                "required": ["game_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Set a reminder that shows a Windows notification at a specified time. Use for 'remind me in X minutes', 'remind me at HH:MM', or 'remind me tomorrow at HH:MM'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The reminder message to show."},
                    "minutes": {"type": "integer", "description": "Minutes from now to show the reminder (e.g. 30 for 'in 30 minutes')."},
                    "time_str": {"type": "string", "description": "Time in HH:MM 24h format (e.g. '15:00' for 3pm)."},
                    "date_str": {"type": "string", "description": "Date in YYYY-MM-DD format. Use with time_str for future dates."}
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agent_task",
            "description": "Execute a complex multi-step task that requires using multiple tools in sequence. Use for: 'research X and save to a file', 'find and organize my photos', 'look up X, summarize it, and copy to clipboard', or any multi-tool automation. NOT for single commands — only use when multiple steps are truly needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "Plain English description of the full task to accomplish."},
                    "priority": {"type": "string", "description": "Task priority: 'normal' or 'high'. High priority tasks will retry harder on failure."}
                },
                "required": ["goal"],
            },
        },
    },

    # ── Web Agent (Live Browser) ────────────────────────────────────────────

    {
        "type": "function",
        "function": {
            "name": "browser_open",
            "description": "Open a URL in a visible browser window that the user can watch. Use this to start web agent tasks like booking flights, filling forms, or navigating websites.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to navigate to (e.g. 'https://google.com/travel/flights'). If no protocol is given, https:// is prepended."}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click a button, link, or element on the current browser page by describing what to click. Tries text matching first, then falls back to vision-based clicking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "A description of the element to click (e.g. 'Search', 'Book Now', 'Accept cookies', 'Next')."}
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_fill",
            "description": "Fill in a form field on the current browser page. Use this to enter names, emails, dates, or any text into input fields.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "description": "The field label, placeholder text, or name (e.g. 'First name', 'Email', 'Departure city')."},
                    "value": {"type": "string", "description": "The value to type into the field."}
                },
                "required": ["field", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_screenshot_analyze",
            "description": "Take a screenshot of the current browser page and analyze it with AI vision. Use this BEFORE clicking or filling to understand what's on screen and confirm the page state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "What to look for or ask about the current page (e.g. 'What flight options are shown?', 'Is there a confirm button?', 'What form fields are visible?')."}
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_scroll",
            "description": "Scroll the current browser page up or down.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "description": "Scroll direction: 'up' or 'down'. Default: 'down'."},
                    "amount": {"type": "integer", "description": "How many scroll steps (each ~300px). Default: 3."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_press_key",
            "description": "Press a keyboard key in the browser (e.g. 'Enter', 'Tab', 'Escape', 'ArrowDown').",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The Playwright key name to press (e.g. 'Enter', 'Tab', 'Escape', 'ArrowDown')."}
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_text",
            "description": "Get the readable text content of the current browser page (scripts and nav elements stripped). Useful for reading search results, prices, or confirmation messages.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_close",
            "description": "Close the visible browser window when the task is complete or the user asks to close it.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },

    # ── Screen Control (Vision-Based) ─────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "click_element",
            "description": (
                "Click on any element visible on the screen using natural language description. "
                "Works for buttons, links, popups, menu items, anything visible. "
                "Uses vision to find the element — works on any screen resolution."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Natural language description of what to click. E.g. 'the Install button', 'the OK button in the popup', 'the second search result'",
                    }
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "handle_popup",
            "description": (
                "Automatically detect and click through Windows confirmation popups, UAC dialogs, "
                "install confirmations, firewall alerts, and similar system dialogs. "
                "Use this whenever you open an app or trigger an installation that may show a popup."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_screen",
            "description": "Scroll the screen up or down.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "Direction to scroll: 'up' or 'down'",
                    },
                    "amount": {
                        "type": "integer",
                        "description": "How much to scroll (1-10, default 3)",
                    },
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "go_back",
            "description": "Press the back button to go to the previous page or screen (Alt+Left).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },

    # ── Screen Control Phase 2 ────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "analyze_screen_context",
            "description": (
                "Take a full screenshot and analyze everything visible on screen — "
                "all buttons, links, items, their positions and descriptions, numbered top to bottom. "
                "Call this before using click_by_index or when you need to understand what's on screen."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_by_index",
            "description": (
                "Click an element by its number on screen. Use after analyze_screen_context. "
                "When user says 'the second one', 'the first result', 'option 3', use the corresponding index."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "The number of the element to click (1 = first, 2 = second, etc.)",
                    }
                },
                "required": ["index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_by_description_contextual",
            "description": (
                "Click an element using natural language with screen context memory. "
                "Use for references like 'that one', 'the red button', 'the other option', 'the cheaper one'. "
                "Uses memory of what's currently on screen."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Natural language description referencing something on screen",
                    }
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "smart_scroll",
            "description": (
                "Scroll screen with natural language amount control. "
                "Use for 'scroll down a bit', 'scroll more', 'scroll up a lot'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "up or down",
                    },
                    "amount": {
                        "type": "string",
                        "description": "Amount to scroll: 'bit', 'little', 'normal', 'more', 'lot'",
                    },
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_multi_step",
            "description": (
                "Execute multiple screen actions in sequence for complex tasks "
                "like 'go to amazon, search for X, click the first result, add to cart'. "
                "Each step has an action and params."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "description": "List of steps to execute in order",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string"},
                                "params": {"type": "object"},
                                "required": {"type": "boolean"},
                            },
                        },
                    }
                },
                "required": ["steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "watch_and_handle_popups",
            "description": (
                "Watch screen and automatically handle any popups that appear for a set duration. "
                "Use after launching apps or starting installations to auto-confirm dialogs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "integer",
                        "description": "How many seconds to watch for popups (default 5)",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_recent_files",
            "description": (
                "Find recent files associated with an application on the user's PC. "
                "Use this when the user asks to open a file for a specific app — "
                "e.g. 'open my Premiere Pro file', 'open my Photoshop project', "
                "'open my Word document', 'open my VS Code project'. "
                "Searches Desktop, Documents, and Downloads for matching file types."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "The application name to find files for (e.g. 'Premiere Pro', 'Photoshop', 'Word').",
                    }
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_file",
            "description": (
                "Open a specific file by its full path using the default application. "
                "Use after find_recent_files to open the file the user wants."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Full path to the file to open.",
                    }
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_projects",
            "description": (
                "Scan and list all code projects found on the user's machine. "
                "Use when the user asks 'what projects do I have', 'show me my projects', "
                "or when you need to find which project to work with."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_project",
            "description": (
                "Find the absolute path of a specific code project by its name across all indexed projects. "
                "Use this when the user asks 'where is my X project', 'open my X project', or needs the path to a specific project."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "The name of the project to find (e.g. 'Ame', 'my-website')."}
                },
                "required": ["project_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_code",
            "description": (
                "Read and analyze code from a project or file to answer questions, "
                "find bugs, explain what the code does, or prepare a fix. "
                "Use when the user asks about code, mentions a file or project by name, "
                "says a specific code file is broken, not working, crashing, or slow. "
                "If the user just says 'help me with this' or 'look at this', use analyze_screen FIRST to see what 'this' is. "
                "ALWAYS call this before attempting to explain or fix any code issue — "
                "never guess without reading the actual code first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What the user wants to know or fix about the code."
                    },
                    "project_hint": {
                        "type": "string",
                        "description": "Project name if the user mentioned one (e.g. 'Ame', 'my-app')."
                    },
                    "file_hint": {
                        "type": "string",
                        "description": "Specific filename if the user mentioned one (e.g. 'server.py', 'App.jsx')."
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the full content of a specific file. "
                "Use when the user explicitly names a file they want you to read, "
                "review, or check. Also use after analyze_code when you need to "
                "read a specific file in full detail."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The filename or path to read (e.g. 'server.py', 'src/App.jsx')."
                    },
                    "project_hint": {
                        "type": "string",
                        "description": "Project name to narrow down which file to read."
                    },
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_fix",
            "description": (
                "Apply a code fix by writing new content to a file. "
                "ONLY call this after the user explicitly confirms they want the fix applied — "
                "either by saying 'yes', 'do it', 'apply it', 'fix it', or similar. "
                "Never call this without user confirmation. "
                "Always creates a .ame.bak backup before writing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Full path to the file to fix."
                    },
                    "fixed_content": {
                        "type": "string",
                        "description": "The complete new file content to write."
                    },
                    "original_content": {
                        "type": "string",
                        "description": "The original file content before the fix (used to create backup)."
                    },
                },
                "required": ["file_path", "fixed_content", "original_content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_file",
            "description": (
                "Find a file by name across all indexed projects on the user's machine. "
                "Use when the user mentions a filename but you need to find its full path."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The filename to search for (e.g. 'server.py', 'config.json')."
                    },
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "semantic_search_code",
            "description": "Search across all indexed code projects by meaning or intent, rather than exact filename. Use this when you want to find 'where the database connection is' or 'the function that calculates rate limits' without knowing the exact file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to look for (e.g. 'API rate limiter logic', 'Discord webhook connection')."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_recent_emails",
            "description": "Read recent emails from the user's Gmail inbox. Use this to check for new messages or find specific emails.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "How many emails to retrieve (default 5)"},
                    "unread_only": {"type": "boolean", "description": "Only fetch unread emails"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email using the user's connected Gmail account. Can include attachments. ALWAYS call this tool immediately when the user asks to send an email. Never just say you will send it without actually calling the tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address or name. If the user asks to send it to themselves (e.g. 'to me', 'to my email'), put 'me' here."},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Main content of the email (optional)"},
                "attachment_path": {"type": "string", "description": "Optional EXACT FULL PATH to a file or folder to attach. Folders are automatically zipped. You MUST use search_files or find_recent_files first to get the absolute path. Do NOT pass just the filename!"}
                },
                "required": ["to", "subject"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_meetings",
            "description": "Retrieve upcoming events and meetings from the user's local Outlook Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "How many days ahead to check (default 1)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "track_orders",
            "description": "Check the user's Gmail for recent online orders, purchases, shipping confirmations, and package tracking updates. Call this when the user asks 'where is my package', 'did I order anything', 'track my orders', or asks about a recent purchase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "How many days back to look for orders (default 14)."}
                }
            }
        }
    },
]
