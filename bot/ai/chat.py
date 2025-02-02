import re

from ollama import Client
from openai import OpenAI

from bot.utils.settings import OLLAMA_MODEL, OLLAMA_SERVER, OPENAI_API_KEY, OPENAI_MODEL

from .prompts import DEFAULT_SYSTEM_PROMPT


class ChatGPT:
    """ChatGPT Class"""

    def __init__(self, system_prompt=DEFAULT_SYSTEM_PROMPT, model=OPENAI_MODEL):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = model
        self.prompt = None
        self.completion = None
        self.files = []
        self.system_prompt = system_prompt
        self.messages = None

    def ask(self, prompt, files: list | None = None, max_tokens: int = 400):
        self.prompt = prompt
        self.files = files[:5] if files else []

        self.messages = [
            {
                "role": "system",
                "content": self.system_prompt,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": self.prompt,
                    },
                    *(
                        [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image}",
                                },
                            }
                            for image in self.files
                        ]
                        if self.files
                        else []
                    ),
                ],
            },
        ]

        self.completion = self.client.chat.completions.create(
            model=self.model, messages=self.messages, max_tokens=max_tokens
        )

        return str(self.completion.choices[0].message.content)

    def get_models(self):
        models_list = self.client.models.list().data
        models = [x.id for x in models_list]

        return sorted(models)


class Ollama:
    """Ollama Class"""

    def __init__(self, model=OLLAMA_MODEL):
        self.client = Client(host=OLLAMA_SERVER)
        self.model = model
        self.prompt = None
        self.completion = None
        self.messages = []

    def ask(self, prompt):
        self.prompt = prompt

        if self.prompt:
            self.messages.append({"role": "user", "content": self.prompt})

        self.completion = self.client.chat(model=self.model, messages=self.messages)
        response = self.completion.get("message").get("content")
        cleaned_response = remove_think_tags(response)

        return cleaned_response


def remove_think_tags(response_content):
    cleaned_content = re.sub(
        r"<think>.*?</think>\s*", "", response_content, flags=re.DOTALL
    )

    return cleaned_content.strip()
