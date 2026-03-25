from openai import AzureOpenAI, RateLimitError, BadRequestError
from aiservice.authentication import BaseAuthentication
from openai.types.chat.chat_completion import (
    ChatCompletion,
    ChatCompletionMessage,
    Choice,
    CompletionUsage,
)
from aiservice.core_functions import generate_random_id
import random, httpx


class OpenAIAssistant:
    def __init__(
        self,
        authentication: BaseAuthentication,
        azure_open_ai_api_endpoint,
        azure_open_ai_api_version,
        prompt_model_deployment_name=None,
        embed_model_deployment_name=None,
    ):
        """
        Initializes the OpenAIAssistant class.

        This class is responsible for interacting with the OpenAI API.

        :param authentication: The BaseAuthentication object for the OpenAI service.
        :param azure_open_ai_api_endpoint: The API endpoint for the OpenAI service.
        :param azure_open_ai_api_version: The API version for the OpenAI service.
        :param prompt_model_deployment_name: The deployment name for the prompt model.
        :param embed_model_deployment_name: The deployment name for the embed model.

        :method prompt: Prompt ChatGPT with a list of messages and get a response.
        :method embed: Embed text using the OpenAI API.
        :method mocking_prompt: Method for mocking the prompt method. This method should be
                used for testing purposes only.
        :method mocking_prompt_rate_limit_error: Method for mocking the prompt method with a
                rate limit error. This method should be used for testing purposes only.
        :method mocking_prompt_jailbreak: Method for mocking the prompt method with a jailbreak
                error. This method should be used for testing purposes only.
        """

        # Fetch deployment for prompting
        if prompt_model_deployment_name:
            self.open_ai_prompt = AzureOpenAI(
                azure_deployment=prompt_model_deployment_name,
                azure_endpoint=azure_open_ai_api_endpoint,
                api_version=azure_open_ai_api_version,
                api_key=authentication.get_token(),
            )
        else:
            self.open_ai_prompt = None

        # Fetch deployment for embedding
        if embed_model_deployment_name:
            self.open_ai_embed = AzureOpenAI(
                azure_deployment=embed_model_deployment_name,
                azure_endpoint=azure_open_ai_api_endpoint,
                api_version=azure_open_ai_api_version,
                api_key=authentication.get_token(),
            )
        else:
            self.open_ai_embed = None

    def prompt(
        self,
        messages,
        temperature=0.0,
        model=None,
        stream=False,
        max_tokens=1024,
        response_format=None,
        **kwargs,
    ):
        """
        Prompt ChatGPT with a list of messages and get a response. Build the array of messages
        for context and call the completion endpoint.

        :param messages: A list of messages comprising the conversation so far.
              [Example Python code](https://cookbook.openai.com/examples/how_to_format_inputs_to_chatgpt_models).

            You can use the roles:
            - system: for system messages
            - user: for user messages
            - assistant: for assistant messages

            Example:
            messages = [
                {"role": "system", "content": "you are a cowboy"},
                {"role": "user", "content":
                    {
                    "type": "text",
                    "text": "What’s in this image?"
                    },
                    {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
                    }
                    }
                },
                {"role": "assistant", "content": "This is a picture of a park."},
                {"role": "user", "content": "Can you tell more about the image above"}
            ]

            image_url can both be a url and a base64 encoded image ("data:image/png;base64,<image_base64>")


        :param temperature: What sampling temperature to use, between 0 and 2. Higher values
              like 0.8 will make the output more random, while lower values like 0.2 will
              make it more focused and deterministic.

        :param model: ID of the model to use. See the
              [model endpoint compatibility](https://platform.openai.com/docs/models/model-endpoint-compatibility)
              table for details on which models work with the Chat API.

        :param stream: If set, partial message deltas will be sent, like in ChatGPT. Tokens
              will be sent as data-only
              [server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events#Event_stream_format)
              as they become available, with the stream terminated by a `data: [DONE]` message.
              [Example Python code](https://cookbook.openai.com/examples/how_to_stream_completions).

        :param max_tokens:  The maximum number of [tokens](/tokenizer) that can be generated
              in the chat completion. The total length of input tokens and generated tokens
              is limited by the model's context length.
              [Example Python code](https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken)
              for counting tokens.

        :response_format: Can be used to force the model to adhere to this structured output format given as a pydantic base model.
        """
        if not self.open_ai_prompt:
            raise ValueError("Prompt model deployment name is not provided.")

        # Call the completion endpoint
        if response_format:
            response = self.open_ai_prompt.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=stream,
                max_tokens=max_tokens,
                response_format=response_format,
                **kwargs,
            )
            return response
        else:
            response = self.open_ai_prompt.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=stream,
                max_tokens=max_tokens,
                **kwargs,
            )
            return response

    def mocking_prompt(
        self, finish_reason="stop", content="Hello, World!", model="gpt-3.5-turbo"
    ):
        """
        Method for mocking the prompt method. This method should be used for testing
        purposes only.

        :param finish_reason: The reason the model stopped generating tokens.
            ['stop', 'length', 'tool_calls', 'content_filter', 'function_call']

        :param content: The content of the message.
        """
        # Generate a random ID for the chat completion
        id = f"chatcmpl-{generate_random_id(32)}"

        # Generate chat completion message object
        message = ChatCompletionMessage(content=content, role="assistant")

        # Generate choices list (choises has one element except for the case when n > 1)
        choices = [
            Choice(
                finish_reason=finish_reason,
                index=0,
                logprobs=None,
                message=message,
            )
        ]

        # Generate usage object
        completion_tokens = random.randint(1, 100)
        prompt_tokens = random.randint(1, 100)

        usage = CompletionUsage(
            completion_tokens=completion_tokens,
            prompt_tokens=prompt_tokens,
            total_tokens=completion_tokens + prompt_tokens,
        )

        return ChatCompletion(
            id=id,
            choices=choices,
            created=0,
            model=model,
            object="chat.completion",
            usage=usage,
        )

    def mocking_prompt_rate_limit_error(self):
        """
        Method for mocking the prompt method with a rate limit error. This method should
        be used for testing purposes only.
        """

        return RateLimitError(
            message="Rate limit exceeded. Please try again later.",
            response=httpx.Response(
                status_code=429, request=httpx.Request("GET", "https://example.com")
            ),
            body=None,
        )

    def mocking_prompt_jailbreak(self):
        """
        Method for mocking the prompt method with a jailbreak error. This method should
        be used for testing purposes only.
        openai.BadRequestError('Error code: 400 - ')
        """

        return BadRequestError(
            message=(
                """Error code: 400 - {\'error\': {\'inner_error\': """
                + """{\'code\': \'ResponsibleAIPolicyViolation\', """
                + """\'content_filter_results\': {\'jailbreak\': {\'filtered\': True, """
                + """\'detected\': True}}}, \'code\': \'content_filter\', """
                + """\'message\': "The response was filtered due to the prompt triggering """
                + """Azure OpenAI\'s content management policy. Please modify your prompt """
                + """and retry. To learn more about our content filtering policies """
                + """please read our documentation: \\r\\nhttps://go.microsoft.com/fwlink/?linkid=2198766.", """
                + """\'param\': \'prompt\', \'type\': None}}"""
            ),
            response=httpx.Response(
                status_code=400,
                request=httpx.Request("GET", "https://example.com"),
                content=(
                    """{\'error\': {\'inner_error\': {\'code\': \'ResponsibleAIPolicyViolation\', """
                    + """\'content_filter_results\': {\'jailbreak\': {\'filtered\': True, """
                    + """\'detected\': True}}}, \'code\': \'content_filter\', """
                    + """\'message\': "The response was filtered due to the prompt triggering """
                    + """Azure OpenAI\'s content management policy. Please modify your prompt """
                    + """and retry. To learn more about our content filtering policies please """
                    + """read our documentation: \\r\\nhttps://go.microsoft.com/fwlink/?linkid=2198766.", """
                    + """\'param\': \'prompt\', \'type\': None}}"""
                ),
            ),
            body=None,
        )

    def embed(self, text, model="text-embedding-3-large", timeout=None):
        """
        Embed text using the OpenAI API.

        :param text: The text to embed.
        :param model: The model to use for embedding.
        :param timeout: The timeout for the request.

        Returns: The embeddings for the text.
        """

        if not self.open_ai_embed:
            raise ValueError("Embed model deployment name is not provided.")

        return self.open_ai_embed.embeddings.create(
            input=text, model=model, timeout=timeout
        )
