# coding=utf-8
# Implements API for ChatGLM3-6B in OpenAI's format. (https://platform.openai.com/docs/api-reference/chat)
# Usage: python openai_api.py
# Visit http://localhost:8000/docs for documents.

# 在OpenAI的API中，max_tokens 等价于 HuggingFace 的 max_new_tokens 而不是 max_length，
# 例如，对于6b模型，设置max_tokens = 8192，则会报错，因为扣除历史记录和提示词后，模型不能输出那么多的tokens。

import os
import time
import json
import urllib
import numpy as np
from contextlib import asynccontextmanager
from typing import Dict, List, Literal, Optional, Union
from enum import Enum

import torch
import uvicorn
import tiktoken
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from transformers import AutoTokenizer, AutoModel
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import PolynomialFeatures
from utils import process_response, generate_chatglm3, generate_stream_chatglm3

MODEL_PATH = os.environ.get('MODEL_PATH', 'THUDM/chatglm3-6b')
TOKENIZER_PATH = os.environ.get("TOKENIZER_PATH", MODEL_PATH)
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'


@asynccontextmanager
async def lifespan(app: FastAPI):  # collects GPU memory
    yield
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Status(Enum):
    SUCCESS = 0
    ERROR = 1

class LaunchInfo(BaseModel):
    status: Status
    message: str

class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "owner"
    root: Optional[str] = None
    parent: Optional[str] = None
    permission: Optional[list] = None


class ModelList(BaseModel):
    object: str = "list"
    data: List[ModelCard] = []


class FunctionCallResponse(BaseModel):
    name: Optional[str] = None
    arguments: Optional[str] = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system", "function"]
    content: str = None
    name: Optional[str] = None
    function_call: Optional[Dict] = None


class DeltaMessage(BaseModel):
    role: Optional[Literal["user", "assistant", "system"]] = None
    content: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.8
    top_p: Optional[float] = 0.8
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    functions: Optional[Union[dict, List[dict]]] = None
    # Additional parameters
    repetition_penalty: Optional[float] = 1.1


class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Literal["stop", "length", "function_call"]


class ChatCompletionResponseStreamChoice(BaseModel):
    index: int
    delta: DeltaMessage
    finish_reason: Optional[Literal["stop", "length", "function_call"]]


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    total_tokens: int = 0
    completion_tokens: Optional[int] = 0


class ChatCompletionResponse(BaseModel):
    model: str
    object: Literal["chat.completion", "chat.completion.chunk"]
    choices: List[Union[ChatCompletionResponseChoice, ChatCompletionResponseStreamChoice]]
    created: Optional[int] = Field(default_factory=lambda: int(time.time()))
    usage: Optional[UsageInfo] = None
    
class EmbeddingRequest(BaseModel):
    input: List[str]
    model: str

class EmbeddingResponse(BaseModel):
    data: list
    model: str
    object: str
    usage: dict


@app.get("/v1/models", response_model=ModelList)
async def list_models():
    model_card = ModelCard(id="chatglm3-6b")
    embedding_card=ModelCard(id="bge-large-zh")
    return ModelList(data=[model_card, embedding_card])


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(request: ChatCompletionRequest):
    global model, tokenizer

    if len(request.messages) < 1 or request.messages[-1].role == "assistant":
        raise HTTPException(status_code=400, detail="Invalid request")

    gen_params = dict(
        messages=request.messages,
        temperature=request.temperature,
        top_p=request.top_p,
        max_tokens=request.max_tokens or 1024,
        echo=False,
        stream=request.stream,
        repetition_penalty=request.repetition_penalty,
        functions=request.functions,
    )

    logger.debug(f"==== request ====\n{gen_params}")

    if request.stream:

        # Use the stream mode to read the first few characters, if it is not a function call, direct stram output
        predict_stream_generator = predict_stream(request.model, gen_params)
        output = next(predict_stream_generator)
        if not contains_custom_function(output):
            return EventSourceResponse(predict_stream_generator, media_type="text/event-stream")

        # Obtain the result directly at one time and determine whether tools needs to be called.
        logger.debug(f"First result output：\n{output}")

        function_call = None
        if output and request.functions:
            try:
                function_call = process_response(output, use_tool=True)
            except:
                logger.warning("Failed to parse tool call")

        # CallFunction
        if isinstance(function_call, dict):
            function_call = FunctionCallResponse(**function_call)


            """
            In this demo, we did not register any tools.
            You can use the tools that have been implemented in our `tool_using` and implement your own streaming tool implementation here.
            Similar to the following method:
                function_args = json.loads(function_call.arguments)
                tool_response = dispatch_tool(tool_name: str, tool_params: dict)
            """
            tool_response = ""

            if not gen_params.get("messages"):
                gen_params["messages"] = []

            gen_params["messages"].append(ChatMessage(
                role="assistant",
                content=output,
            ))
            gen_params["messages"].append(ChatMessage(
                role="function",
                name=function_call.name,
                content=tool_response,
            ))

            # Streaming output of results after function calls
            generate = predict(request.model, gen_params)
            return EventSourceResponse(generate, media_type="text/event-stream")

        else:
            # Handled to avoid exceptions in the above parsing function process.
            generate = parse_output_text(request.model, output)
            return EventSourceResponse(generate, media_type="text/event-stream")

    # Here is the handling of stream = False
    response = generate_chatglm3(model, tokenizer, gen_params)

    # Remove the first newline character
    if response["text"].startswith("\n"):
        response["text"] = response["text"][1:]
    response["text"] = response["text"].strip()
    usage = UsageInfo()
    function_call, finish_reason = None, "stop"
    if request.functions:
        try:
            function_call = process_response(response["text"], use_tool=True)
        except:
            logger.warning("Failed to parse tool call, maybe the response is not a tool call or have been answered.")

    if isinstance(function_call, dict):
        finish_reason = "function_call"
        function_call = FunctionCallResponse(**function_call)

    message = ChatMessage(
        role="assistant",
        content=response["text"],
        function_call=function_call if isinstance(function_call, FunctionCallResponse) else None,
    )

    logger.debug(f"==== message ====\n{message}")

    choice_data = ChatCompletionResponseChoice(
        index=0,
        message=message,
        finish_reason=finish_reason,
    )
    task_usage = UsageInfo.model_validate(response["usage"])
    for usage_key, usage_value in task_usage.model_dump().items():
        setattr(usage, usage_key, getattr(usage, usage_key) + usage_value)
    return ChatCompletionResponse(model=request.model, choices=[choice_data], object="chat.completion", usage=usage)

@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def get_embeddings(request: EmbeddingRequest):
    # 计算嵌入向量和tokens数量
    embeddings = [EMBEDDING_MODEL.encode(text) for text in request.input]

    # 如果嵌入向量的维度不为1536，则使用插值法扩展至1536维度
    embeddings = [
        expand_features(embedding, 1536) if len(embedding) < 1536 else embedding
        for embedding in embeddings
    ]

    # Min-Max normalization 归一化
    embeddings = [embedding / np.linalg.norm(embedding) for embedding in embeddings]

    # 将numpy数组转换为列表
    embeddings = [embedding.tolist() for embedding in embeddings]
    prompt_tokens = sum(len(text.split()) for text in request.input)
    total_tokens = sum(num_tokens_from_string(text) for text in request.input)

    response = {
        "data": [
            {"embedding": embedding, "index": index, "object": "embedding"}
            for index, embedding in enumerate(embeddings)
        ],
        "model": request.model,
        "object": "list",
        "usage": {
            "prompt_tokens": prompt_tokens,
            "total_tokens": total_tokens,
        },
    }

    return response

def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding('cl100k_base')
    num_tokens = len(encoding.encode(string))
    return num_tokens

async def predict(model_id: str, params: dict):
    global model, tokenizer

    choice_data = ChatCompletionResponseStreamChoice(
        index=0,
        delta=DeltaMessage(role="assistant"),
        finish_reason=None
    )
    chunk = ChatCompletionResponse(model=model_id, choices=[choice_data], object="chat.completion.chunk")
    yield "{}".format(chunk.model_dump_json(exclude_unset=True))

    previous_text = ""
    for new_response in generate_stream_chatglm3(model, tokenizer, params):
        decoded_unicode = new_response["text"]
        delta_text = decoded_unicode[len(previous_text):]
        previous_text = decoded_unicode

        finish_reason = new_response["finish_reason"]
        if len(delta_text) == 0 and finish_reason != "function_call":
            continue

        function_call = None
        if finish_reason == "function_call":
            try:
                function_call = process_response(decoded_unicode, use_tool=True)
            except:
                logger.warning(
                    "Failed to parse tool call, maybe the response is not a tool call or have been answered.")

        if isinstance(function_call, dict):
            function_call = FunctionCallResponse(**function_call)

        delta = DeltaMessage(
            content=delta_text,
            role="assistant",
            function_call=function_call if isinstance(function_call, FunctionCallResponse) else None,
        )

        choice_data = ChatCompletionResponseStreamChoice(
            index=0,
            delta=delta,
            finish_reason=finish_reason
        )
        chunk = ChatCompletionResponse(model=model_id, choices=[choice_data], object="chat.completion.chunk")
        yield "{}".format(chunk.model_dump_json(exclude_unset=True))

    choice_data = ChatCompletionResponseStreamChoice(
        index=0,
        delta=DeltaMessage(),
        finish_reason="stop"
    )
    chunk = ChatCompletionResponse(model=model_id, choices=[choice_data], object="chat.completion.chunk")
    yield "{}".format(chunk.model_dump_json(exclude_unset=True))
    yield '[DONE]'


def predict_stream(model_id, gen_params):
    """
    The function call is compatible with stream mode output.

    The first seven characters are determined.
    If not a function call, the stream output is directly generated.
    Otherwise, the complete character content of the function call is returned.

    :param model_id:
    :param gen_params:
    :return:
    """
    output = ""
    is_function_call = False
    has_send_first_chunk = False
    for new_response in generate_stream_chatglm3(model, tokenizer, gen_params):
        decoded_unicode = new_response["text"]
        delta_text = decoded_unicode[len(output):]
        output = decoded_unicode

        # When it is not a function call and the character length is> 7,
        # try to judge whether it is a function call according to the special function prefix
        if not is_function_call and len(output) > 7:

            # Determine whether a function is called
            is_function_call = contains_custom_function(output)
            if is_function_call:
                continue

            # Non-function call, direct stream output
            finish_reason = new_response["finish_reason"]

            # Send an empty string first to avoid truncation by subsequent next() operations.
            if not has_send_first_chunk:
                message = DeltaMessage(
                    content="",
                    role="assistant",
                    function_call=None,
                )
                choice_data = ChatCompletionResponseStreamChoice(
                    index=0,
                    delta=message,
                    finish_reason=finish_reason
                )
                chunk = ChatCompletionResponse(model=model_id, choices=[choice_data], object="chat.completion.chunk")
                yield "{}".format(chunk.model_dump_json(exclude_unset=True))

            send_msg = delta_text if has_send_first_chunk else output
            has_send_first_chunk = True
            message = DeltaMessage(
                content=send_msg,
                role="assistant",
                function_call=None,
            )
            choice_data = ChatCompletionResponseStreamChoice(
                index=0,
                delta=message,
                finish_reason=finish_reason
            )
            chunk = ChatCompletionResponse(model=model_id, choices=[choice_data], object="chat.completion.chunk")
            yield "{}".format(chunk.model_dump_json(exclude_unset=True))

    if is_function_call:
        yield output
    else:
        yield '[DONE]'

async def parse_output_text(model_id: str, value: str):
    """
    Directly output the text content of value

    :param model_id:
    :param value:
    :return:
    """
    choice_data = ChatCompletionResponseStreamChoice(
        index=0,
        delta=DeltaMessage(role="assistant", content=value),
        finish_reason=None
    )
    chunk = ChatCompletionResponse(model=model_id, choices=[choice_data], object="chat.completion.chunk")
    yield "{}".format(chunk.model_dump_json(exclude_unset=True))

    choice_data = ChatCompletionResponseStreamChoice(
        index=0,
        delta=DeltaMessage(),
        finish_reason="stop"
    )
    chunk = ChatCompletionResponse(model=model_id, choices=[choice_data], object="chat.completion.chunk")
    yield "{}".format(chunk.model_dump_json(exclude_unset=True))
    yield '[DONE]'

def contains_custom_function(value: str) -> bool:
    """
    Determine whether 'function_call' according to a special function prefix.

    For example, the functions defined in "tool_using/tool_register.py" are all "get_xxx" and start with "get_"

    [Note] This is not a rigorous judgment method, only for reference.

    :param value:
    :return:
    """
    return value and 'get_' in value

def expand_features(embedding, target_length):
    poly = PolynomialFeatures(degree=2)
    expanded_embedding = poly.fit_transform(embedding.reshape(1, -1))
    expanded_embedding = expanded_embedding.flatten()
    if len(expanded_embedding) > target_length:
        # 如果扩展后的特征超过目标长度，可以通过截断或其他方法来减少维度
        expanded_embedding = expanded_embedding[:target_length]
    elif len(expanded_embedding) < target_length:
        # 如果扩展后的特征少于目标长度，可以通过填充或其他方法来增加维度
        expanded_embedding = np.pad(
            expanded_embedding, (0, target_length - len(expanded_embedding))
        )
    return expanded_embedding

def log_launch_info(status: Status, port: int = 0, message: str = None):
    if status == Status.SUCCESS:
        data = LaunchInfo(status = status, message =f"http://localhost:{port}")
    else:
        data = LaunchInfo(status = status, message = message)
    print(data.model_dump_json(exclude_unset=True))
    
def get_port(defaultPort: int):
    port = defaultPort
    with open('config.json', 'r') as f:
        config = json.load(f)
        if 'base_url' in config:
            url_parts = urllib.parse.urlparse(config['base_url'])
            port = url_parts.port
    return port

if __name__ == "__main__":

    try:
        tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH, trust_remote_code=True)
        if 'cuda' in DEVICE:  # AMD, NVIDIA GPU can use Half Precision
            model = AutoModel.from_pretrained(MODEL_PATH, trust_remote_code=True).to(DEVICE).eval()

            # Multi-GPU support, use the following two lines instead of the above line, num gpus to your actual number of graphics cards
            # from utils import load_model_on_gpus
            # model = load_model_on_gpus(MODEL_PATH, num_gpus=2)

        else:  # CPU, Intel GPU and other GPU can use Float16 Precision Only
            model = AutoModel.from_pretrained(MODEL_PATH, trust_remote_code=True).float().to(DEVICE).eval()
        EMBEDDING_MODEL = SentenceTransformer('BAAI/bge-large-zh-v1.5', device=DEVICE)
        port = get_port(8600)
        log_launch_info(Status.SUCCESS, port=port)
        uvicorn.run(app, host='0.0.0.0', port=port, workers=1)
    except Exception as e:
        print(e)
        log_launch_info(Status.ERROR, message='Service launch failed')