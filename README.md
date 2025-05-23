# Arch Chan - Your Cute Anime Girl AI Assistant

![Arch Chan](https://raw.githubusercontent.com/berkucuk/Arch-Chan-AI/refs/heads/main/icons/arch-chan.png)

## Project Overview

**Arch Chan** is no ordinary virtual assistant; she's a **cute anime girl who loves Arch Linux** and is designed to be your **friendly, daily companion**! She's here to be your cheerful chat partner and guide through the tech world. Arch Chan doesn't just answer your questions; she brightens your day with her sweet voice, energetic personality, and anime-themed charm.

Forget the usual, mundane assistants. **Arch Chan** brings a refreshing, delightful touch to your interactions with her anime-inspired charm, making your daily conversations both helpful and entertaining. She's ideal for anime lovers, Arch Linux enthusiasts, or anyone looking for a friendly assistant that truly stands out from the crowd. Every chat with her transforms into an experience that is both informative and enjoyable.

![Arch Chan](https://raw.githubusercontent.com/berkucuk/Arch-Chan-AI/refs/heads/main/ui-v2.0.png)

## Key Features

Arch Chan is more than just an AI; she offers a suite of unique features that enrich the user experience:

-   **Friendly Daily AI Companion**: Arch Chan is built not just to answer your questions but to be your **daily AI companion**, engaging in friendly conversations, sharing tips, and adding a touch of fun to your routine.
-   **Anime Girl Personality**: She's not just a bot – Arch Chan is an **anime girl** who brings personality, warmth, and charm to every chat. She speaks sweetly and lovingly, creating a welcoming atmosphere for every conversation. 🌸
-   **Arch Linux Enthusiast**: As a huge fan of **Arch Linux**, Arch Chan is always ready to discuss everything Arch-related, from system configurations to the latest updates. You can confidently ask her your Linux questions.
-   **Intelligent Conversations with Gemini AI**: Powered by **Google's Gemini AI model**, Arch Chan provides intelligent, context-aware responses, making your conversations more engaging and insightful. Her LangChain integration ensures advanced natural language understanding and processing capabilities.
-   **Multilingual Communication**: Interact with Arch Chan in your preferred language. The application supports various languages for a personalized experience.
-   **Voice Interaction (Text-to-Speech)**: Arch Chan can speak her responses aloud using advanced text-to-speech (TTS) capabilities, providing a more natural and engaging interaction. Volume control is also available.
-   **Dynamic Command Execution**: Arch Chan can understand and execute Linux commands based on your requests, returning the command outputs directly within the chat. This feature provides great convenience for technical users.
-   **System Information & Task Management**: Get insights into your system's status and manage basic tasks through Arch Chan (e.g., CPU usage, memory status).
-   **File Integrity Checks**: Utilize Arch Chan to perform file hashing, ensuring the integrity and authenticity of your files.
-   **Robust Client-Server Architecture**: The application is built on a stable client-server model, ensuring efficient and concurrent handling of multiple user interactions. Each client connection is managed in a separate thread for optimized performance.
-   **Intuitive Graphical User Interface (GUI)**: Built with PyQt5, the user-friendly interface offers a seamless experience for chatting, viewing responses, and managing settings. Its clean and elegant design is easy on the eyes.
-   **Comprehensive Logging & Error Handling**: Both the client and server components feature robust logging and error handling, ensuring application stability and ease of debugging. Potential issues are promptly identified and logged.
-   **Secure Configuration with Environment Variables**: API keys and other sensitive configurations are securely loaded from environment variables via a `.env` file. This ensures both security and ease of setup.

Arch Chan's sweet, cute tone is perfect for a comforting chat, whether you need some help or just want to relax with a friendly anime assistant.

## Architecture

The Arch Chan project is built upon a robust client-server architecture:

-   **`mcp_server.py` (Server)**:
    -   Acts as the central processing unit.
    -   Communicates with **Google Gemini AI** and processes AI responses.
    -   Handles prompt management and output parsing using **LangChain**.
    -   Analyzes incoming user messages and generates context-aware responses.
    -   Can execute Linux commands, provide system information, and perform special functions like file hashing.
    -   Manages multiple client connections concurrently using **threading**. Each client maintains its own chat history and language preference independently (for future development).
    -   Utilizes environment variables (`.env`) for security.
    -   Processes command execution requests via XML parsing.
    -   Server logging is crucial for monitoring operational status and potential issues.

-   **`gui_chatbot.py` (Client - GUI)**:
    -   Provides the visual interface for user interaction.
    -   Developed using **PyQt5**, offering a modern and interactive user experience.
    -   Sends user-typed messages to the server and displays responses received from the server.
    -   Enables text-to-speech functionality using **gTTS** (Google Text-to-Speech) and **Pygame**, allowing you to hear Arch Chan's voice. Volume control is available.
    -   Supports multiple languages and manages user language preferences.
    -   Visual details like the application icon enhance the user experience.
    -   Comprehensive error handling and logging are critical for identifying client-side issues.

These two main components ensure Arch Chan operates as a smooth and interactive AI assistant.

## Installation

Getting started with **Arch Chan** is simple. Just follow the steps below to set up your own personal anime assistant:

1.  **Clone the repository**:
    ```bash
    git clone [https://github.com/berkucuk/Arch-Chan-AI.git](https://github.com/berkucuk/Arch-Chan-AI.git)
    cd Arch-Chan-AI
    ```

2.  **Run the installation script**:
    ```bash
    chmod +x install.sh
    sudo ./install.sh
    ```
    This script will install all necessary dependencies and prepare your environment to run Arch Chan.

3.  **Choose your preferred language**: Arch Chan will ask you to select your language to ensure the experience feels just right.

4.  **Start chatting**: Once installation is complete, you can begin interacting with Arch Chan! Whether you’re in the mood for a friendly chat or some tech tips, Arch Chan is always ready.

### Development Environment Setup (Optional)

If you wish to develop or modify Arch Chan, follow these steps to set up a development environment:

1.  Clone the repository as described above.
2.  Ensure you have Python 3.8+ installed.
3.  Create and activate a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate # Linux/macOS
    # venv\Scripts\activate # Windows
    ```
4.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```
5.  Rename the `.env.example` file to `.env` and add your Google Gemini API key:
    ```
    GOOGLE_API_KEY="your_google_gemini_api_key_here"
    ```
6.  Start the server:
    ```bash
    python3 mcp_server.py
    ```
7.  In a separate terminal, start the GUI:
    ```bash
    python3 gui_chatbot.py
    ```

## Usage

After installation, **Arch Chan** becomes your go-to assistant for all kinds of conversations:

-   Discuss **Arch Linux** tips, tricks, and advice.
-   Enjoy casual chat about **anime**, **hobbies**, or anything that brings a smile to your face.
-   Receive simple help with everyday tasks, such as setting reminders or staying motivated.
-   **Execute Linux commands** and view their outputs directly.
-   Get **system information** and perform **task management** operations.
-   Verify **file integrity** using hashing functions.

Arch Chan isn’t just an assistant – she’s a **charming companion** who makes every interaction feel personal, fun, and helpful. She is here to make your day just a little brighter with her cute, cheerful personality.

## Contributing

We welcome contributions to make Arch Chan even better! If you'd like to contribute to the project, please follow these steps:

1.  Fork the repository.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

All feedback and contributions are welcome!

## Future Plans

We aim to continuously improve Arch Chan. Some of our future plans include:

-   **Enhanced Memory Management**: More sophisticated chat history and memory capabilities for longer, more context-aware conversations.
-   **Visual Interactions**: More dynamic animations and visuals within Arch Chan's GUI to further express her personality.
-   **More Integrations**: Expanding integrations with popular tools and services.
-   **Web Interface**: Offering a web interface option in addition to the GUI.
-   **User Profiles**: Implementing user profiles and preferences for a more personalized experience.
-   **Modular Structure**: Developing a more modular code structure to easily add new features and functionalities.

## License

The **Arch Chan** project is distributed under the MIT License. See the `LICENSE` file for full details.

---

Enjoy your daily interactions with **Arch Chan** and treat her like your best friend! ✨
