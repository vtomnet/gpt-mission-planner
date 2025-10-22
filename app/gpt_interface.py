import logging
import time


from dotenv import load_dotenv
import litellm
from litellm import completion

from context import rap_2026_context, verification_agent_context

logger = logging.getLogger(__name__)

class LLMInterface:
    def __init__(self):
        self.logger: logging.Logger = logger
        load_dotenv()
        # schema text
        self.schemas: str = ""
        # context
        self.context = []
        self.initial_context_length: int = 0
        # input template file provided when wanting spin verification
        self.promela_template: str = ""

    def init_context(self, schema_path: list[str], context_files: list[str]):
        for s in schema_path:
            # all robots must come with a schema
            self._set_schema(s)

        # context can be updated from context.py
        self.context = rap_2026_context(self.schemas)

        # this could be empty
        if context_files is not None:
            if len(context_files) > 0:
                self.context += self._add_additional_context_files(context_files)

        self.initial_context_length = len(self.context)

    def init_promela_context(
        self,
        schema_path: list[str],
        promela_template: str,
        context_files: list[str],
    ):
        for s in schema_path:
            # all robots must come with a schema
            self._set_schema(s)

        # default context
        self.context = verification_agent_context(self.schemas, promela_template)

        # this could be empty
        if context_files is not None:
            if len(context_files) > 0:
                self.context += self._add_additional_context_files(context_files)

        self.initial_context_length = len(self.context)

    def add_context(self, user: str, assistant: str | None = None) -> None:
        # generate new GPT API dict string context
        new_user_context = {"role": "user", "content": user}
        # append to pre-existing context
        self.context.append(new_user_context)
        # do the same if you want to capture response
        if assistant is not None:
            new_assistant_context = {"role": "assistant", "content": assistant}
            self.context.append(new_assistant_context)

    def reset_context(self, context_count: int):
        self.context = self.context[0:context_count]

    def ask_gpt(self, prompt: str, model: str, add_context: bool = False) -> str | None:
        answered = False
        message = self.context.copy() + [{"role": "user", "content": prompt}]
        print("MODEL:", model)
        print("MESSAGES:", message)

        while not answered:
            try:
                cmp = completion(
                    model=model,
                    messages=message,
                )
                answered = True
            except litellm.exceptions.RateLimitError as e:
                self.logger.warning(f"Rate limit error: {e}")
                time.sleep(1)  # wait before retrying

        response: str | None = cmp.choices[0].message.content

        if add_context:
            self.add_context(prompt, response)

        return response

    def _set_schema(self, schema_path: str) -> None:
        # Read XSD from 1872.1-2024
        with open(schema_path, "r") as file:
            self.schemas += file.read()

        self.schemas += "\nThis schema is located at path: " + schema_path

        # deliniate for llm
        self.schemas += "\nnext schema: "

    def _add_additional_context_files(self, context_files: list[str]):
        context_list = []
        for c in context_files:
            with open(c, "r") as file:
                extra = file.read()
            context_list.append(
                {
                    "role": "user",
                    "content": "Use this additional file to provide context when generating XML mission plans. \
                            The content within should be self explanatory: "
                    + extra,
                }
            )

        return context_list
