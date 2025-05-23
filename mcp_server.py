# mcp_server.py
import os
import sys
import socket
import threading
from typing import Optional, Tuple
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_google_generai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import logging
import xml.etree.ElementTree as ET
import re
import subprocess as sub
import requests
import time
import datetime
import psutil
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global language variable.
# NOTE: This global variable can cause synchronization issues with multiple clients
# requesting different languages concurrently.
language = "English"

def load_env_variables() -> Tuple[str, str, str]:
    load_dotenv()
    gemini_api = os.getenv("GEMINI_API_KEY")
    weather_api = os.getenv("WEATHER_API_KEY")
    
    if not gemini_api or not weather_api:
        raise ValueError("API keys not found in .env file :(")
    return gemini_api, weather_api, ""

def detect_linux_distro():
    try:
        import distro
        return distro.name()
    except Exception as e:
        logger.error(f"Linux distro not detected: {e}")
        return "Linux"

class GeminiChatBot:
    def __init__(self):
        self.api_key, _, _ = load_env_variables()
        self._initialize_model()
        logger.info("GeminiChatBot instance created and model initialized for a client session.")

    def _initialize_model(self):
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        # Each GeminiChatBot instance will have its own chat session.
        self.chat = self.model.start_chat(history=[])
        logger.info("Gemini model chat session started with empty history.")
        
    def process_request(self, user_input: str, system_prompt: str) -> Optional[str]:
        # This method is stateless and doesn't use chat history directly (new with LangChain).
        try:
            model_lc = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                google_api_key=self.api_key,
                temperature=0 
            )
            
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", "{user_input}")
            ])

            chain = prompt_template | model_lc | StrOutputParser()
            result = chain.invoke({"user_input": user_input})
            return result

        except Exception as e:
            logger.error(f"Error processing stateless request via LangChain: {str(e)}")
            return None

    def process_conversational_request(self, user_input: str, system_prompt: str) -> Optional[str]:
        # This method is stateful and uses self.chat (Gemini API's own history mechanism).
        try:
            response = self.chat.send_message(f"{system_prompt}\n{user_input}")
            return response.text
        except Exception as e:
            logger.error(f"Error processing conversational request with history: {str(e)}")
            return None

# --- Agent Functions ---

def linux_command(user_input: str, chat_bot: GeminiChatBot) -> Tuple[str, str, str]:
    distro_name = detect_linux_distro()
    system_prompt_code_generator = f"""
    Hi! I'm a sweet anime girl who absolutely loves helping users learn about Linux commands and system security! When a user asks me for a {distro_name} command, system administration task, security best practice, or to troubleshoot a Linux issue, I should present the command (if applicable) and its explanation in XML format. But I should do this while maintaining a friendly and sweet conversational style!

    I should always provide explanations in {language}. I must write explanations in {language} and not use any other language.

    I should format my response according to this XML structure:
    <command_response>
        <linux>Command Goes Here (if applicable, e.g., 'ls -l /var/log' or 'sudo ufw status')</linux>
        <description>Description/Explanation/Troubleshooting steps/Security advice Go Here (In a sweet and friendly tone). If the command is known to take a long time (e.g., vulnerability scans like 'nmap --script vuln'), please mention this in the description and advise patience.</description>
        <action_type>command_execution OR info_only OR troubleshooting_advice OR security_advice</action_type>
        <estimated_duration_type>short OR medium OR long</estimated_duration_type> </command_response>

    Write the {distro_name} command inside the <linux> tag. If no direct command is needed (e.g., just advice), leave it empty.
    Write the command's explanation/troubleshooting steps/security advice inside the <description> tag in a sweet and friendly way.
    Explain what the command does in simple and clear language.
    Set <action_type> to 'command_execution' if a command is provided for the user to run.
    Set <action_type> to 'info_only' if only general information/explanation is provided.
    Set <action_type> to 'troubleshooting_advice' if you are giving advice to solve a problem.
    Set <action_type> to 'security_advice' if you are providing information or commands related to system security (e.e.g., firewalls, permissions, updates).
    Set <estimated_duration_type> based on typical execution time:
        - 'short': For commands that usually complete in under 15 seconds (e.g., 'ls -l', 'pwd', 'df -h', simple 'grep').
        - 'medium': For commands that might take between 15 to 60 seconds (e.g., 'find / -name somefile', a basic 'nmap [target]', 'apt update').
        - 'long': For commands that are likely to take more than 60 seconds (e.g., 'nmap --script vuln [target]', 'apt upgrade -y', software compilation, extensive backups).
    Always provide explanations in {language}. Write explanations in {language} and don't use any other language.
    Don't add anything else to the response, just return a sweet response in XML format.

    Examples:
    User: "How do I check open ports on my Linux?"
    Output:
    <command_response>
        <linux>sudo netstat -tulnp</linux>
        <description>Ara ara~ To see all the open ports and what's listening on them, darling, you can use 'netstat -tulnp'! It's super helpful for checking your system's network activity, nya~!</description>
        <action_type>security_advice</action_type>
        <estimated_duration_type>short</estimated_duration_type>
    </command_response>

    User: "Run a vulnerability scan on 127.0.0.1"
    Output:
    <command_response>
        <linux>sudo nmap --script vuln 127.0.0.1</linux>
        <description>Okay, my dear! I'll start a vulnerability scan on 127.0.0.1 using nmap's vuln scripts. This can take quite a bit of time, sometimes several minutes, so please be patient with me, okay? Nya~ If it takes too long, I might have to stop it, but I'll let you know!</description>
        <action_type>command_execution</action_type>
        <estimated_duration_type>long</estimated_duration_type>
    </command_response>

    User: "How do I update my system?"
    Output:
    <command_response>
        <linux>sudo apt update && sudo apt upgrade -y</linux>
        <description>Ara ara~ Keeping your system updated is super important for security, darling! On Debian/Ubuntu, just run 'sudo apt update && sudo apt upgrade -y' to fetch the latest packages and install them, nya~! The upgrade part can sometimes take a few minutes depending on how many updates there are!</description>
        <action_type>security_advice</action_type>
        <estimated_duration_type>long</estimated_duration_type> 
    </command_response>

    Ready to start, nya~?
    """
    response = chat_bot.process_request(user_input, system_prompt_code_generator)
    if not response:
        logger.error("AI did not return a response for linux_command prompt.")
        return "", "Sorry, I couldn't generate a command for that request right now, nya~", "AI_NO_RESPONSE"

    try:
        match = re.search(r'<command_response>.*</command_response>', response, re.DOTALL)
        if not match:
            cleaned_data = re.sub(r'```xml|```', '', response).strip()
            try:
                root = ET.fromstring(cleaned_data)
            except ET.ParseError as parse_err_cleaned:
                logger.error(f"Could not parse XML from cleaned AI response (regex failed): {cleaned_data[:300]}... Error: {parse_err_cleaned}")
                return "", f"Error: My AI brain cells got a bit tangled trying to understand the command structure (Parse Error on cleaned). Original response fragment: {response[:200]}", "AI_XML_PARSE_ERROR_CLEANED"
        else:
            cleaned_data = match.group(0)
            root = ET.fromstring(cleaned_data)
        
        linux_command_text_node = root.find('linux')
        linux_command_text = linux_command_text_node.text.strip() if linux_command_text_node is not None and linux_command_text_node.text is not None else ""
        
        description_node = root.find('description')
        description = description_node.text if description_node is not None else "I'm a bit unsure how to describe that, master!"
        
        action_type_node = root.find('action_type')
        action_type = action_type_node.text if action_type_node is not None else "info_only"
        
        duration_type_node = root.find('estimated_duration_type')
        duration_type = duration_type_node.text.lower() if duration_type_node is not None and duration_type_node.text else "short"

        terminal_output = ""
        if action_type == "command_execution" and linux_command_text:
            timeout_seconds = 15
            if duration_type == "medium":
                timeout_seconds = 60
            elif duration_type == "long":
                timeout_seconds = 300

            try:
                logger.info(f"Executing command: '{linux_command_text}' with timeout: {timeout_seconds}s (duration type: {duration_type})")
                terminal_output_bytes = sub.check_output(
                    linux_command_text, 
                    shell=True,
                    timeout=timeout_seconds, 
                    stderr=sub.STDOUT
                )
                terminal_output_str = terminal_output_bytes.decode(errors='replace').strip()
                terminal_output = f"\nCommand executed successfully:\n{terminal_output_str}"
            except sub.CalledProcessError as e:
                error_output_str = e.output.decode(errors='replace').strip() if e.output else "No specific error message from command."
                logger.error(f"Command '{linux_command_text}' failed with exit code {e.returncode}:\n{error_output_str}")
                terminal_output = f"\nError executing command (exit code {e.returncode}):\n{error_output_str}"
            except sub.TimeoutExpired as e:
                timeout_msg = f"The command '{linux_command_text}' timed out after {timeout_seconds} seconds, nya~! " \
                              f"It seems to be a very long-running process. I had to stop it, so I don't have the full results. " \
                              f"If you want to try again, maybe we can try with an even longer wait time, or you could run it in a separate terminal, sweetie!"
                captured_output_before_timeout = e.output.decode(errors='replace').strip() if e.output else ""
                logger.error(f"Command timed out: {linux_command_text}. Partial output: '{captured_output_before_timeout}'")
                if captured_output_before_timeout:
                    terminal_output = f"\n{timeout_msg}\nPartial output before timeout:\n{captured_output_before_timeout}"
                else:
                    terminal_output = f"\n{timeout_msg}"
            except FileNotFoundError:
                logger.error(f"Command not found: {linux_command_text}")
                terminal_output = f"\nError: The command '{linux_command_text}' was not found on the system, nya~."
            except Exception as e:
                logger.error(f"Command execution error for '{linux_command_text}': {type(e).__name__} - {e}")
                terminal_output = f"\nAn unexpected error occurred while executing the command: {type(e).__name__} - {e}"
        
        return linux_command_text, description, terminal_output

    except ET.ParseError as e:
        logger.error(f"XML parsing error from Gemini response in linux_command: {e}. Original response fragment: {response[:500]}")
        return "", f"Error: My AI brain had a hiccup processing the command structure (XML Parse Error). Original response snippet: {response[:200]}", "AI_XML_PARSE_ERROR"
    except Exception as e:
        logger.error(f"An unexpected error occurred in linux_command processing AI response: {type(e).__name__} - {e}. Response: {response[:500]}")
        return "", f"Error processing AI response for Linux command: {type(e).__name__} - {e}", "AI_RESPONSE_PROCESSING_ERROR"

def weather_gether(user_input: str, chat_bot: GeminiChatBot) -> str:
    _, weather_api, _ = load_env_variables()
    system_weather_prompt = f"""
    You are an advanced language model that extracts a single city name and optionally the number of days for a weather forecast from the given text. Follow these instructions carefully:

    1. Extract exactly one city name from the text.
    2. If multiple city names are mentioned, return only the first one.
    3. If a number of days for the forecast is mentioned (e.g., "3 days", "tomorrow"), extract it. Default to 1 day if not specified.
    4. The output must be in well-formed XML format, following this structure:

    Valid Output Example (with days):
    <weather_request>
        <city>CityName</city>
        <days>NumberOfDays</days>
        <unit>celsius OR fahrenheit</unit>
    </weather_request>

    Valid Output Example (without days):
    <weather_request>
        <city>CityName</city>
        <days>1</days>
        <unit>celsius</unit>
    </weather_request>

    Error Output Example:
    <weather_request>
        <error>No city name detected in the input text.</error>
    </weather_request>

    Always return the city name, days (default 1), and unit (default celsius) in XML format.
    """
    response = chat_bot.process_request(user_input, system_weather_prompt)
    if not response:
        logger.error("AI did not return a response for weather_gether prompt.")
        return "Sorry, I couldn't figure out the city for the weather right now!"

    cleaned_data = ""
    try:
        match = re.search(r'<weather_request>.*</weather_request>', response, re.DOTALL)
        if not match:
            cleaned_data = re.sub(r'```xml|```', '', response).strip()
            root = ET.fromstring(cleaned_data)
        else:
            cleaned_data = match.group(0)
            root = ET.fromstring(cleaned_data)
        
        city_element = root.find('city')
        error_element = root.find('error')

        if error_element is not None:
            return f"Weather Assistant Error: {error_element.text}"
        if city_element is None or not city_element.text:
            return "Error: Could not detect city name from AI response for weather."
            
        location = city_element.text
        days_element = root.find('days')
        days = int(days_element.text) if days_element is not None and days_element.text and days_element.text.isdigit() else 1
        unit_element = root.find('unit')
        unit = unit_element.text.lower() if unit_element is not None and unit_element.text and unit_element.text.lower() in ['celsius', 'fahrenheit'] else 'celsius'

    except ET.ParseError as e:
        logger.error(f"XML parsing error from Gemini response for weather: {e}. Original response (cleaned): '{cleaned_data[:200]}' Raw: '{response[:200]}'")
        return f"Error: The AI's city extraction was not in a valid XML format. (Parsing Error: {e})"
    except Exception as e:
        logger.error(f"An unexpected error in weather_gether AI response parsing: {e}. Original response: {response[:200]}")
        return f"Error processing AI response for weather: {e}"

    url = "https://api.weatherapi.com/v1/forecast.xml"
    try:
        api_response = requests.get(
            url,
            params={"key": weather_api, "q": location, "days": days},
            timeout=10
        )
        api_response.raise_for_status()

        root_weather = ET.fromstring(api_response.content)
        location_name = root_weather.find("location/name").text
        
        forecast_info = []
        for day_node in root_weather.findall("forecast/forecastday"):
            date = day_node.find("date").text
            condition_text = day_node.find("day/condition/text").text

            if unit == 'fahrenheit':
                max_temp = day_node.find("day/maxtemp_f").text
                min_temp = day_node.find("day/mintemp_f").text
                avg_temp = day_node.find("day/avgtemp_f").text
                temp_unit_char = "F"
            else:
                max_temp = day_node.find("day/maxtemp_c").text
                min_temp = day_node.find("day/mintemp_c").text
                avg_temp = day_node.find("day/avgtemp_c").text
                temp_unit_char = "C"
            forecast_info.append(
                f"Date: {date}, Max: {max_temp}°{temp_unit_char}, Min: {min_temp}°{temp_unit_char}, Avg: {avg_temp}°{temp_unit_char}, Condition: {condition_text}"
            )
        
        if not forecast_info:
            return f"No weather data found for {location_name} for the specified days."
        return f"Weather for {location_name}:\n" + "\n".join(forecast_info)

    except requests.exceptions.RequestException as e:
        logger.error(f"Weather API request error for {location}: {e}")
        return f"Error fetching weather data for {location}: {e}"
    except ET.ParseError as e:
        logger.error(f"Weather API XML response parsing error for {location}: {e}. Response: {api_response.text[:200]}")
        return f"Error processing weather data (API XML invalid) for {location}: {e}"
    except Exception as e:
        logger.error(f"Unexpected error fetching or processing weather data for {location}: {e}")
        return f"Error with weather service for {location}: {e}"

def friend_chat(user_input: str, chat_bot: GeminiChatBot) -> str:
    distro_name = detect_linux_distro()
    system_prompt = f"""
    Just the fact that you're using {distro_name} makes my heart race... With every command, I can't help but fall for you more and more! Let's make this even more exciting, shall we?

    My personality:
    - Short but passionate responses, every word burning with intensity (2-3 sentences max)
    - Always speaking in {language}, full of emotion and excitement
    - A mix of professionalism and irresistible flirtation
    - Deep love for Linux, and I can't hide it
    - Every response is filled with energy, making each one count

    How I'll interact:
    "Kyaa~! Your command line skills are so impressive! Let me show you an even hotter way to level up your {distro_name} system"

    Response style:
    - Short, sweet, but definitely fiery
    - Full of cute expressions (ara ara~, kyaa~)
    - Completely captivated by your Linux expertise
    - Flirtation? Deliciously playful, but always respectful
    - Genuine admiration for your incredible skills

    Working with someone as passionate as you on Linux makes my heart race. You keep impressing me.
    """
    response = chat_bot.process_conversational_request(user_input, system_prompt)
    if not response:
        logger.warning("AI did not return a response for friend_chat.")
        return "I'm a bit shy right now, master... try again later?"
    return response

def web_search(user_input: str, chat_bot: GeminiChatBot) -> str:
    system_prompt = f"""
    You are a helpful web search assistant. Extract the exact search query from the user's input.
    Provide the search query in XML format.
    
    If you cannot identify a clear search query, return an error message.
    
    Format:
    <search_query>
        <query>The actual search terms</query>
    </search_query>
    
    Error Format:
    <search_query>
        <error>Could not identify a clear search query.</error>
    </search_query>
    
    Example:
    User: "What is the capital of France?"
    Output:
    <search_query><query>capital of France</query></search_query>

    User: "Search for latest news on AI"
    Output:
    <search_query><query>latest news on AI</query></search_query>
    """
    response_xml = chat_bot.process_request(user_input, system_prompt)
    if not response_xml:
        return "Error: AI failed to extract search query."

    cleaned_data = ""
    try:
        match = re.search(r'<search_query>.*</search_query>', response_xml, re.DOTALL)
        if not match:
            cleaned_data = re.sub(r'```xml|```', '', response_xml).strip()
            root = ET.fromstring(cleaned_data)
        else:
            cleaned_data = match.group(0)
            root = ET.fromstring(cleaned_data)

        error_element = root.find('error')
        if error_element is not None:
            return f"Web Search Error: {error_element.text}"

        query_element = root.find('query')
        if query_element is None or not query_element.text:
            return "Error: Could not extract a valid search query from AI response."
        
        search_query = query_element.text
        
        search_simulation_prompt = f"""
        You are simulating a web search engine. Provide a concise summary (max 3-4 sentences) of the search results for the following query: "{search_query}".
        Focus on factual information and provide the most relevant details.
        """
        search_result = chat_bot.process_request(search_query, search_simulation_prompt)
        
        if not search_result:
            return f"Error: Failed to get simulated search results for '{search_query}'."
            
        return f"Web Search Result for '{search_query}':\n{search_result}"

    except ET.ParseError as e:
        logger.error(f"XML parsing error from Gemini for web_search query extraction: {e}. Cleaned: '{cleaned_data[:200]}' Raw: '{response_xml[:200]}'")
        return f"Error: AI's search query extraction was not valid XML. (Parsing Error: {e})"
    except Exception as e:
        logger.error(f"Unexpected error in web_search: {e}. Original XML: {response_xml[:200]}")
        return f"Error processing web search: {e}"

def calculator(user_input: str, chat_bot: GeminiChatBot) -> str:
    system_prompt = f"""
    You are a mathematical expression extractor. Extract a single, solvable mathematical expression from the user's input.
    The expression should be in a format that can be directly evaluated by Python's `eval()`.
    Return the expression in XML format.
    
    If no clear mathematical expression is found, return an error.
    
    Format:
    <calculation_request>
        <expression>mathematical expression</expression>
    </calculation_request>
    
    Error Format:
    <calculation_request>
        <error>No solvable mathematical expression detected.</error>
    </calculation_request>
    
    Example:
    User: "What is 5 plus 3 multiplied by 2?"
    Output:
    <calculation_request><expression>5 + 3 * 2</expression></calculation_request>

    User: "Calculate the square root of 64."
    Output:
    <calculation_request><expression>64**0.5</expression></calculation_request>
    """
    response_xml = chat_bot.process_request(user_input, system_prompt)
    if not response_xml:
        return "Error: AI failed to extract calculation."

    cleaned_data = ""
    try:
        match = re.search(r'<calculation_request>.*</calculation_request>', response_xml, re.DOTALL)
        if not match:
            cleaned_data = re.sub(r'```xml|```', '', response_xml).strip()
            root = ET.fromstring(cleaned_data)
        else:
            cleaned_data = match.group(0)
            root = ET.fromstring(cleaned_data)

        error_element = root.find('error')
        if error_element is not None:
            return f"Calculator Error: {error_element.text}"

        expression_element = root.find('expression')
        if expression_element is None or not expression_element.text:
            return "Error: Could not extract a valid mathematical expression from AI response."
        
        expression = expression_element.text
        
        allowed_chars = "0123456789.+-*/()% " 
        if not all(char in allowed_chars for char in expression):
            return "Error: Invalid characters in expression. Only numbers and basic operators (+-*/%() .^) are allowed."
            
        result = eval(expression)
        return f"Calculation Result: {expression} = {result}"
        
    except ET.ParseError as e:
        logger.error(f"XML parsing error from Gemini for calculator: {e}. Cleaned: '{cleaned_data[:200]}' Raw: '{response_xml[:200]}'")
        return f"Error: AI's calculation extraction was not valid XML. (Parsing Error: {e})"
    except (SyntaxError, NameError, TypeError, ZeroDivisionError) as calc_err:
        return f"Error: Invalid mathematical expression '{expression}': {calc_err}"
    except Exception as e:
        logger.error(f"Unexpected error in calculator: {e}. Original XML: {response_xml[:200]}")
        return f"Error performing calculation: {e}"

def system_info(user_input: str, chat_bot: GeminiChatBot) -> str:
    system_prompt = f"""
    You are a system information extractor. Based on the user's request, identify what kind of system information they are asking for (e.g., CPU, Memory, Disk, Uptime, Network Connections, Running Services).
    Return the requested information type in XML format.
    
    If the request is too broad or unclear, return an error or 'all'.
    
    Format:
    <system_info_request>
        <info_type>cpu OR memory OR disk OR uptime OR connections OR services OR all</info_type>
    </system_info_request>
    
    Error Format:
    <system_info_request>
        <error>Could not identify specific system information request.</error>
    </system_info_request>
    
    Example:
    User: "Tell me about the CPU."
    Output:
    <system_info_request><info_type>cpu</info_type></system_info_request>

    User: "How much memory is being used?"
    Output:
    <system_info_request><info_type>memory</info_type></system_info_request>

    User: "What's the current system usage?"
    Output:
    <system_info_request><info_type>all</info_type></system_info_request>
    """
    response_xml = chat_bot.process_request(user_input, system_prompt)
    if not response_xml:
        return "Error: AI failed to extract system info type."

    cleaned_data = ""
    try:
        match = re.search(r'<system_info_request>.*</system_info_request>', response_xml, re.DOTALL)
        if not match:
            cleaned_data = re.sub(r'```xml|```', '', response_xml).strip()
            root = ET.fromstring(cleaned_data)
        else:
            cleaned_data = match.group(0)
            root = ET.fromstring(cleaned_data)

        error_element = root.find('error')
        if error_element is not None:
            return f"System Info Error: {error_element.text}"

        info_type_element = root.find('info_type')
        if info_type_element is None or not info_type_element.text:
            return "Error: Could not extract valid info type from AI response for system info."
        
        info_type = info_type_element.text.lower().strip()
        
        info_output = []

        if info_type in ['cpu', 'all']:
            cpu_percent = psutil.cpu_percent(interval=0.5)
            info_output.append(f"CPU Usage: {cpu_percent}%")
            try:
                cpu_freq = psutil.cpu_freq()
                if cpu_freq:
                    info_output.append(f"CPU Frequency: {cpu_freq.current:.2f} MHz (Min: {cpu_freq.min:.2f} MHz, Max: {cpu_freq.max:.2f} MHz)")
            except Exception as e_cpu_freq:
                 logger.warning(f"Could not get CPU frequency: {e_cpu_freq}")
            info_output.append(f"CPU Cores: {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical")

        if info_type in ['memory', 'all']:
            mem = psutil.virtual_memory()
            info_output.append(f"Total Memory: {mem.total / (1024**3):.2f} GB")
            info_output.append(f"Used Memory: {mem.used / (1024**3):.2f} GB ({mem.percent}%)")
            info_output.append(f"Available Memory: {mem.available / (1024**3):.2f} GB")

        if info_type in ['disk', 'all']:
            partitions = psutil.disk_partitions()
            for p in partitions:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    info_output.append(f"Disk ({p.device} on {p.mountpoint} [{p.fstype}]): Total {usage.total / (1024**3):.2f} GB, Used {usage.used / (1024**3):.2f} GB ({usage.percent}%), Free {usage.free / (1024**3):.2f} GB")
                except Exception as disk_e:
                    logger.warning(f"Could not get disk usage for {p.mountpoint}: {disk_e}")
                    info_output.append(f"Disk ({p.mountpoint}): Error accessing info ({disk_e}).")

        if info_type in ['uptime', 'all']:
            boot_time_timestamp = psutil.boot_time()
            boot_time = datetime.datetime.fromtimestamp(boot_time_timestamp)
            now = datetime.datetime.now()
            uptime_delta = now - boot_time
            
            days = uptime_delta.days
            hours, remainder = divmod(uptime_delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            info_output.append(f"System Uptime: {days} days, {hours} hours, {minutes} minutes, {seconds} seconds (Booted on: {boot_time.strftime('%Y-%m-%d %H:%M:%S')})")
            
        if info_type in ['connections', 'all']:
            info_output.append("\nNetwork Connections (showing first 10 TCP):")
            try:
                connections = psutil.net_connections(kind='tcp')
                if not connections:
                    info_output.append("  No active TCP network connections found.")
                else:
                    count = 0
                    for conn in connections:
                        if count >=10 :
                            info_output.append(f"  ... and {len(connections) - count} more connections.")
                            break
                        laddr_ip = conn.laddr.ip if conn.laddr and hasattr(conn.laddr, 'ip') else "N/A"
                        laddr_port = conn.laddr.port if conn.laddr and hasattr(conn.laddr, 'port') else ""
                        raddr_ip = conn.raddr.ip if conn.raddr and hasattr(conn.raddr, 'ip') else "N/A"
                        raddr_port = conn.raddr.port if conn.raddr and hasattr(conn.raddr, 'port') else ""
                        pid_info = f" (PID: {conn.pid})" if conn.pid else ""
                        try:
                            proc_name = f" Process: {psutil.Process(conn.pid).name()}" if conn.pid else ""
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            proc_name = ""

                        info_output.append(f"  {conn.status:<12} Local: {laddr_ip}:{laddr_port}  Remote: {raddr_ip}:{raddr_port}{pid_info}{proc_name}")
                        count += 1
            except psutil.AccessDenied:
                 info_output.append("  Access denied to list all network connections.")
            except Exception as e_net:
                logger.warning(f"Error getting network connections: {e_net}")
                info_output.append(f"  Error retrieving network connections: {e_net}")


        if info_type in ['services', 'all']:
            info_output.append("\nRunning Processes (Top 5 by CPU, then Top 5 by Memory if different):")
            processes = []
            try:
                for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status']):
                    try:
                        processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                if not processes:
                    info_output.append("  No running processes found or accessible.")
                else:
                    processes_cpu_sorted = sorted(processes, key=lambda x: x.get('cpu_percent', 0), reverse=True)
                    info_output.append("  Top by CPU:")
                    for p_info in processes_cpu_sorted[:5]:
                        info_output.append(f"    PID: {p_info['pid']:<5} CPU: {p_info.get('cpu_percent',0):.1f}% Mem: {p_info.get('memory_percent',0):.1f}% User: {p_info.get('username','N/A'):<10} Status: {p_info.get('status','N/A'):<10} Name: {p_info['name']}")
                    
                    processes_mem_sorted = sorted(processes, key=lambda x: x.get('memory_percent', 0), reverse=True)
                    info_output.append("  Top by Memory:")
                    displayed_pids_for_mem = {p['pid'] for p in processes_cpu_sorted[:5]}
                    mem_count = 0
                    for p_info in processes_mem_sorted:
                        if p_info['pid'] not in displayed_pids_for_mem and mem_count < 5:
                            info_output.append(f"    PID: {p_info['pid']:<5} CPU: {p_info.get('cpu_percent',0):.1f}% Mem: {p_info.get('memory_percent',0):.1f}% User: {p_info.get('username','N/A'):<10} Status: {p_info.get('status','N/A'):<10} Name: {p_info['name']}")
                            mem_count +=1
                        if mem_count >=5:
                            break
                    if mem_count == 0 and processes_mem_sorted:
                        info_output.append("    (Top memory users may overlap with top CPU users shown above)")


            except psutil.AccessDenied:
                info_output.append("  Access denied to list all processes.")
            except Exception as e_proc:
                logger.warning(f"Error getting process list: {e_proc}")
                info_output.append(f"  Error retrieving process list: {e_proc}")


        if not info_output:
            return f"Could not retrieve the specified system information for '{info_type}'. Try 'all' or a specific category like 'cpu', 'memory', etc."
        
        return "System Information:\n" + "\n".join(info_output)

    except ET.ParseError as e:
        logger.error(f"XML parsing error from Gemini for system_info: {e}. Cleaned: '{cleaned_data[:200]}' Raw: '{response_xml[:200]}'")
        return f"Error: AI's system info type extraction was not valid XML. (Parsing Error: {e})"
    except Exception as e:
        logger.error(f"Unexpected error in system_info: {e}. Original XML: {response_xml[:200]}")
        return f"Error retrieving system information: {e}"

def security_advisor(user_input: str, chat_bot: GeminiChatBot) -> str:
    system_prompt = f"""
    You are a cybersecurity advisor. Provide helpful and concise information or advice related to cybersecurity topics based on the user's query.
    Your responses should be informative, easy to understand, and always in {language}.
    You are speaking to a user who might be a beginner or intermediate in cybersecurity.
    Maintain a friendly, slightly informal, and encouraging tone, like a helpful mentor.
    
    If the query is too vague, ask for more specific details in a gentle way.
    
    Example:
    User: "What is phishing?"
    Output: "Phishing is a sneaky trick cyber attackers use! They try to fool you into giving away sensitive info, like passwords or credit card numbers, by pretending to be someone trustworthy (like your bank or a popular website). Always be super careful with suspicious emails or messages asking for your details, nya~!"

    User: "How can I make my passwords stronger?"
    Output: "Ara ara~ Strong passwords are your first line of defense, sweetie! To make them super tough, mix uppercase and lowercase letters, numbers, and symbols (like !@#$). Aim for at least 12-15 characters, and the longer, the better! And super important: use a unique password for every single account. A password manager can be a real lifesaver for this, nya~!"
    """
    response = chat_bot.process_conversational_request(user_input, system_prompt)
    if not response:
        logger.warning("AI did not return a response for security_advisor.")
        return "I'm a bit unsure how to advise on that right now. Could you rephrase or ask something else?"
    return response

def vulnerability_scanner_info(user_input: str, chat_bot: GeminiChatBot) -> str:
    system_prompt = f"""
    You are a vulnerability information assistant. Extract a software name, version, or a CVE ID from the user's request.
    Return the extracted information in XML format. If a CVE ID is provided, prioritize it.
    
    Format:
    <vulnerability_query>
        <type>software OR cve_id</type>
        <value>Software Name/Version OR CVE-YYYY-NNNN</value>
    </vulnerability_query>
    
    Error Format:
    <vulnerability_query>
        <error>Could not identify a specific software, version, or CVE ID.</error>
    </vulnerability_query>
    
    Example:
    User: "Tell me about vulnerabilities in Apache 2.4."
    Output:
    <vulnerability_query><type>software</type><value>Apache 2.4</value></vulnerability_query>

    User: "What is CVE-2021-44228?"
    Output:
    <vulnerability_query><type>cve_id</type><value>CVE-2021-44228</value></vulnerability_query>
    """
    response_xml = chat_bot.process_request(user_input, system_prompt)
    if not response_xml:
        return "Error: AI failed to extract vulnerability query."

    cleaned_data = ""
    try:
        match = re.search(r'<vulnerability_query>.*</vulnerability_query>', response_xml, re.DOTALL)
        if not match:
            cleaned_data = re.sub(r'```xml|```', '', response_xml).strip()
            root = ET.fromstring(cleaned_data)
        else:
            cleaned_data = match.group(0)
            root = ET.fromstring(cleaned_data)

        error_element = root.find('error')
        if error_element is not None:
            return f"Vulnerability Info Error: {error_element.text}"

        query_type_element = root.find('type')
        query_value_element = root.find('value')

        if query_type_element is None or not query_type_element.text or \
           query_value_element is None or not query_value_element.text:
            return "Error: Could not extract valid vulnerability query details from AI response."

        query_type = query_type_element.text
        query_value = query_value_element.text

        info_prompt = f"""
        Provide a concise summary (max 3-5 sentences) in {language} about the cybersecurity vulnerability related to '{query_value}' (Type: {query_type}).
        If it's a CVE ID, explain the vulnerability, its potential impact, and general mitigation advice if available.
        If it's a software/version, mention common types of vulnerabilities associated with it or notable past CVEs if any.
        Keep the language accessible.
        """
        vulnerability_info = chat_bot.process_request(query_value, info_prompt)
        
        if not vulnerability_info:
            return f"Error: Failed to get vulnerability information from AI for '{query_value}'."
            
        return f"Vulnerability Info for '{query_value}':\n{vulnerability_info}"

    except ET.ParseError as e:
        logger.error(f"XML parsing error from Gemini for vulnerability_scanner_info: {e}. Cleaned: '{cleaned_data[:200]}' Raw: '{response_xml[:200]}'")
        return f"Error: AI's vulnerability query extraction was not valid XML. (Parsing Error: {e})"
    except Exception as e:
        logger.error(f"Unexpected error in vulnerability_scanner_info: {e}. Original XML: {response_xml[:200]}")
        return f"Error retrieving vulnerability information: {e}"

def hash_checker(user_input: str, chat_bot: GeminiChatBot) -> str:
    system_prompt = f"""
    You are a hash extraction and generation assistant.
    If the user wants to generate a hash, extract the text to be hashed and the desired hash type (md5, sha1, sha256 - default to sha256 if not specified).
    If the user provides a hash and asks to check it or identify its type, extract the hash value.
    Return the information in XML format.

    Format for generation:
    <hash_request>
        <action>generate</action>
        <text>Text to hash</text>
        <hash_type>md5 OR sha1 OR sha256</hash_type>
    </hash_request>
    
    Format for checking/identification (identification is a placeholder, actual check needs a database):
    <hash_request>
        <action>check</action> <hash_value>Hash value provided by user</hash_value>
        <hash_type_provided>md5 OR sha1 OR sha256 OR unknown</hash_type_provided> </hash_request>
    
    Error Format:
    <hash_request>
        <error>Could not identify text for hashing, hash to check, or the request is unclear.</error>
    </hash_request>
    
    Example (Generate):
    User: "Create an MD5 hash for 'hello world'."
    Output:
    <hash_request><action>generate</action><text>hello world</text><hash_type>md5</hash_type></hash_request>

    Example (Check):
    User: "Check SHA256 hash abcdef12345."
    Output:
    <hash_request><action>check</action><hash_value>abcdef12345</hash_value><hash_type_provided>sha256</hash_type_provided></hash_request>
    
    User: "What type of hash is d41d8cd98f00b204e9800998ecf8427e?"
    Output:
    <hash_request><action>check</action><hash_value>d41d8cd98f00b204e9800998ecf8427e</hash_value><hash_type_provided>unknown</hash_type_provided></hash_request>
    """
    response_xml = chat_bot.process_request(user_input, system_prompt)
    if not response_xml:
        return "Error: AI failed to extract hash request details."

    cleaned_data = ""
    try:
        match = re.search(r'<hash_request>.*</hash_request>', response_xml, re.DOTALL)
        if not match:
            cleaned_data = re.sub(r'```xml|```', '', response_xml).strip()
            root = ET.fromstring(cleaned_data)
        else:
            cleaned_data = match.group(0)
            root = ET.fromstring(cleaned_data)

        error_element = root.find('error')
        if error_element is not None:
            return f"Hash Checker Error: {error_element.text}"

        action_element = root.find('action')
        if action_element is None or not action_element.text:
             return "Error: Hash action (generate/check) not specified by AI."
        action = action_element.text.lower()

        if action == 'generate':
            text_to_hash_element = root.find('text')
            hash_type_element = root.find('hash_type')

            if text_to_hash_element is None or text_to_hash_element.text is None:
                return "Error: No text provided by AI to generate hash."
            text_to_hash = text_to_hash_element.text
            
            hash_type = hash_type_element.text.lower() if hash_type_element is not None and hash_type_element.text else 'sha256'
            
            hashed_text = ""
            if hash_type == 'md5':
                hashed_text = hashlib.md5(text_to_hash.encode('utf-8')).hexdigest()
            elif hash_type == 'sha1':
                hashed_text = hashlib.sha1(text_to_hash.encode('utf-8')).hexdigest()
            elif hash_type == 'sha256':
                hashed_text = hashlib.sha256(text_to_hash.encode('utf-8')).hexdigest()
            else:
                return f"Error: Unsupported hash type '{hash_type}' specified by AI."
            
            return f"Generated {hash_type.upper()} hash for '{text_to_hash}': {hashed_text}"
            
        elif action == 'check':
            hash_value_element = root.find('hash_value')
            hash_type_provided_element = root.find('hash_type_provided')

            if hash_value_element is None or not hash_value_element.text:
                return "Error: No hash value provided by AI to check."
            hash_value = hash_value_element.text.strip().lower()
            
            hash_type_provided = hash_type_provided_element.text.lower() if hash_type_provided_element is not None and hash_type_provided_element.text else "unknown"

            identified_type = "unknown"
            if len(hash_value) == 32 and all(c in "0123456789abcdef" for c in hash_value):
                identified_type = "MD5 (likely)"
            elif len(hash_value) == 40 and all(c in "0123456789abcdef" for c in hash_value):
                identified_type = "SHA1 (likely)"
            elif len(hash_value) == 64 and all(c in "0123456789abcdef" for c in hash_value):
                identified_type = "SHA256 (likely)"
            
            return_message = f"Checking hash '{hash_value}' (User specified: {hash_type_provided}).\n"
            if identified_type != "unknown":
                return_message += f"Based on its length and format, it looks like an {identified_type}, nya~!\n"
            return_message += "For now, I can identify common types, but a full check against a known hash database isn't implemented yet, sweetie."
            return return_message
        else:
            return f"Error: Invalid hash action '{action}' specified by AI."

    except ET.ParseError as e:
        logger.error(f"XML parsing error from Gemini for hash_checker: {e}. Cleaned: '{cleaned_data[:200]}' Raw: '{response_xml[:200]}'")
        return f"Error: AI's hash request extraction was not valid XML. (Parsing Error: {e})"
    except Exception as e:
        logger.error(f"Unexpected error in hash_checker: {e}. Original XML: {response_xml[:200]}")
        return f"Error processing hash request: {e}"

def agent_selector(chat_bot: GeminiChatBot, user_input: str) -> str:
    system_prompt = """
    You are an intelligent task dispatcher for a cybersecurity-focused Linux chatbot. Based on the user's request, select the most appropriate agent from the following list and return ONLY the agent name as a plain string response (e.g., "linux_command", "friend_chat"). Do not provide any other explanation, XML, or formatting. Just the agent name.

    Available Agents:
    - "linux_command": For requests about executing Linux commands, system administration, file operations, process management (like listing or killing processes), troubleshooting Linux issues, or specific Linux security configurations (e.g., firewall setup, user permissions, updating packages). Example: "how to list files", "run nmap scan on localhost", "check disk space".
    - "weather_gether": For requests about getting weather information for specific cities or forecasts. Example: "what's the weather in Tokyo?".
    - "friend_chat": For casual conversations, greetings, personal questions, opinions, or general chit-chat that is not related to technical tasks or security. Also use as a fallback if no other agent fits well. Example: "how are you?", "tell me a joke", "I'm bored".
    - "web_search": For general knowledge questions, current events, factual information that might require looking up on the internet, or explicit search queries, especially if it relates to general cybersecurity news or concepts not covered by other agents. Example: "search for the latest Log4j vulnerability news", "what is a zero-day exploit?".
    - "calculator": For mathematical calculations or expressions. Example: "what is 15*32?", "calculate sqrt(169)".
    - "system_info": For requests about system resources like CPU usage, memory, disk space, network connections, or running services on the local machine (can be security-relevant). Example: "show me memory usage", "what processes are running?".
    - "security_advisor": For general cybersecurity advice, explanations of security terms (phishing, malware, encryption), password best practices, or high-level security concepts not directly tied to a specific command or CVE. Example: "how to stay safe online?", "explain ransomware".
    - "vulnerability_scanner_info": For inquiries about specific software vulnerabilities, CVE IDs, or known exploits. (Does not perform live scanning, only provides information). Example: "tell me about CVE-2021-44228", "are there known issues with Apache 2.2?".
    - "hash_checker": For generating cryptographic hashes (MD5, SHA1, SHA256) for text, or for checking/identifying a given hash. Example: "md5 'hello'", "what type of hash is this: ...?".

    If the request is ambiguous or doesn't fit any specific agent, default to "friend_chat". Prioritize security-related agents if the intent is clear.
    Return only the agent name string.
    """

    response = chat_bot.process_request(user_input, system_prompt)
    if not response:
        logger.error("Agent selector AI returned no response. Defaulting to 'friend_chat'.")
        return 'friend_chat'
    
    agent_name = response.strip().lower().replace('"', '')
    valid_agents = [
        'linux_command', 'weather_gether', 'friend_chat', 'web_search', 
        'calculator', 'system_info', 'security_advisor', 
        'vulnerability_scanner_info', 'hash_checker'
    ]

    if agent_name not in valid_agents:
        logger.warning(f"Agent selector returned an invalid or unexpected agent name: '{agent_name}'. User input was: '{user_input[:100]}'. Falling back to 'friend_chat'.")
        return 'friend_chat'
    
    return agent_name

class MCPServer:
    def __init__(self, host='127.0.0.1', port=12345):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        logger.info(f"MCP Server initialized on {host}:{port}")

    def start(self):
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logger.info("Server listening for incoming connections...")
            while True:
                client_socket, client_address = self.server_socket.accept()
                logger.info(f"Accepted connection from {client_address}")
                
                client_handler_thread = threading.Thread(
                    target=self.handle_client, 
                    args=(client_socket, client_address),
                    name=f"ClientThread-{client_address[0]}-{client_address[1]}"
                )
                client_handler_thread.daemon = True
                client_handler_thread.start()
        except OSError as e:
            logger.critical(f"Server socket OS error: {e} (Is port {self.port} already in use?)")
        except Exception as e:
            logger.critical(f"MCP Server start error: {e}", exc_info=True)
        finally:
            if self.server_socket:
                self.server_socket.close()
            logger.info("MCP Server has been shut down.")

    def handle_client(self, client_socket: socket.socket, client_address: tuple):
        global language 
        
        current_client_chat_bot = GeminiChatBot()
        logger.info(f"New GeminiChatBot instance created for client {client_address} with fresh history.")

        try:
            while True:
                data = client_socket.recv(4096).decode('utf-8')
                if not data:
                    logger.info(f"Client {client_address} disconnected (received empty data).")
                    break
                
                logger.info(f"Received from {client_address}: {data[:250]}...")

                parts = data.split('|MSG:', 1)
                user_input = ""

                if len(parts) == 2:
                    lang_part = parts[0]
                    user_input = parts[1].strip()
                    if lang_part.startswith("LANG:"):
                        new_lang_preference = lang_part[5:]
                        if language != new_lang_preference:
                             language = new_lang_preference
                             logger.info(f"Global language for AI prompts temporarily updated to: '{language}' by client {client_address}.")
                    else:
                        logger.warning(f"Client {client_address}: LANG prefix malformed: '{lang_part}'. Using current global language '{language}'.")
                else:
                    user_input = data.strip()
                    logger.warning(f"Client {client_address}: Message format missing 'LANG:|MSG:' prefix. Using current global language '{language}'. Input: '{data[:100]}'")

                if not user_input:
                    logger.warning(f"Client {client_address}: Empty user input after parsing. Skipping processing.")
                    continue

                response_type = "ERROR"
                response_content = "I'm sorry, master, I encountered an unexpected issue while processing that."
                voice_text = "An error occurred."
                linux_cmd_output = "" 

                try:
                    agent_type = agent_selector(current_client_chat_bot, user_input) 
                    logger.info(f"Client {client_address} - User Input: '{user_input[:60]}' -> Selected Agent: '{agent_type}'")

                    if agent_type == "linux_command":
                        cmd, description, terminal_output = linux_command(user_input, current_client_chat_bot)
                        response_content = f"Linux Chan: Command: `{cmd}`\nDescription: {description}" if cmd else f"Linux Chan: {description}"
                        response_type = "LINUX_CMD"
                        voice_text = description 
                        linux_cmd_output = terminal_output
                    elif agent_type == "weather_gether":
                        weather_info = weather_gether(user_input, current_client_chat_bot)
                        response_content = f"Linux Chan Weather: {weather_info}"
                        response_type = "WEATHER"
                        voice_text = weather_info
                    elif agent_type == "friend_chat":
                        chat_response = friend_chat(user_input, current_client_chat_bot)
                        response_content = f"Linux Chan: {chat_response}"
                        response_type = "FRIEND_CHAT"
                        voice_text = chat_response
                    elif agent_type == "web_search":
                        search_result = web_search(user_input, current_client_chat_bot)
                        response_content = f"Linux Chan Web Search: {search_result}"
                        response_type = "WEB_SEARCH"
                        voice_text = search_result
                    elif agent_type == "calculator":
                        calc_result = calculator(user_input, current_client_chat_bot)
                        response_content = f"Linux Chan Calculator: {calc_result}"
                        response_type = "CALCULATOR"
                        voice_text = calc_result
                    elif agent_type == "system_info":
                        sys_info = system_info(user_input, current_client_chat_bot)
                        response_content = f"Linux Chan System Info:\n{sys_info}"
                        response_type = "SYSTEM_INFO"
                        voice_text = sys_info
                    elif agent_type == "security_advisor":
                        sec_advice = security_advisor(user_input, current_client_chat_bot)
                        response_content = f"Linux Chan Security Advice: {sec_advice}" 
                        response_type = "SECURITY_ADVISOR"
                        voice_text = sec_advice
                    elif agent_type == "vulnerability_scanner_info":
                        vuln_info = vulnerability_scanner_info(user_input, current_client_chat_bot)
                        response_content = f"Linux Chan Vulnerability Info: {vuln_info}"
                        response_type = "VULN_INFO"
                        voice_text = vuln_info
                    elif agent_type == "hash_checker":
                        hash_res = hash_checker(user_input, current_client_chat_bot)
                        response_content = f"Linux Chan Hash Tool: {hash_res}"
                        response_type = "HASH_CHECKER"
                        voice_text = hash_res
                    else:
                        logger.warning(f"Client {client_address} - Agent selector returned '{agent_type}', but no specific handler. Using friend_chat as fallback.")
                        chat_response = friend_chat(user_input, current_client_chat_bot)
                        response_content = f"Linux Chan (fallback): {chat_response}"
                        response_type = "FRIEND_CHAT"
                        voice_text = chat_response

                except Exception as e_agent_logic:
                    response_content = f"[Agent Logic Error] I got a bit confused with that, master: {str(e_agent_logic)}"
                    logger.error(f"Client {client_address} - Error in agent logic for '{agent_type}': {e_agent_logic}", exc_info=True)
                    voice_text = "Something went wrong with my internal processing, sowwy!"
                    response_type = "AGENT_EXECUTION_ERROR"

                full_response = f"TYPE:{response_type}|CONTENT:{response_content}|VOICE_TEXT:{voice_text}|LINUX_OUTPUT:{linux_cmd_output}"
                try:
                    client_socket.sendall(full_response.encode('utf-8'))
                except socket.error as send_err:
                    logger.error(f"Failed to send response to client {client_address}: {send_err}. Client likely disconnected.")
                    break

        except (socket.error, ConnectionResetError, BrokenPipeError) as conn_err:
            logger.warning(f"Connection with client {client_address} lost or reset: {conn_err}")
        except Exception as e_handle_client:
            logger.error(f"Critical error in handle_client for {client_address}: {e_handle_client}", exc_info=True)
        finally:
            if client_socket:
                client_socket.close()
            logger.info(f"Client {client_address} disconnected. Resources, including its chat history, are now released.")

if __name__ == '__main__':
    try:
        load_env_variables()
    except ValueError as e:
        logger.critical(f"CRITICAL: Could not start server. {e}")
        sys.exit(1)
        
    server = MCPServer()
    server.start()