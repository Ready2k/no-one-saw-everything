"""
Author: Joon Sung Park (joonspk@stanford.edu)

File: gpt_structure.py
Description: Wrapper functions for calling OpenAI APIs.
Patched to use the LocalLLM gateway (http://127.0.0.1:8080/v1) instead of
OpenAI. Legacy openai.Completion calls are bridged to chat completions because
local models only expose the chat endpoint. Embeddings use sentence-transformers
so no embedding model needs to be running separately.
"""
import json
import os
import random
import signal
import openai
import openai.api_requestor as _oai_req
import time

from utils import *

# Hard wall-clock timeout for any single LLM call. signal.alarm sends SIGALRM
# after N seconds and interrupts blocking network I/O — unlike request_timeout
# which only fires if no bytes arrive, this fires even when the server is slowly
# trickling tokens back.
LLM_TIMEOUT_S = 90

def _sigalrm_handler(signum, frame):
    raise TimeoutError(f"LLM call exceeded {LLM_TIMEOUT_S}s wall-clock limit")

def _llm_call(fn):
    """Call fn() with a hard SIGALRM timeout. Returns the result or raises."""
    old_handler = signal.signal(signal.SIGALRM, _sigalrm_handler)
    signal.alarm(LLM_TIMEOUT_S)
    try:
        return fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

openai.api_key  = openai_api_key
openai.api_base = openai_api_base  # point at local gateway

# Patch only the openai session to trust the LocalLLM self-signed cert.
# We do this surgically so other libraries (HuggingFace etc.) are unaffected.
_orig_make_session = _oai_req._make_session
def _local_session():
    s = _orig_make_session()
    # Trust the self-signed gateway cert. Fail closed: if the cert file is
    # missing we keep verify=True (the default) rather than disabling TLS.
    if os.path.exists(local_cert):
        s.verify = local_cert
    else:
        import warnings
        warnings.warn(
            f"LocalLLM cert not found at {local_cert}; TLS verification may fail.",
            RuntimeWarning, stacklevel=2,
        )
    return s
_oai_req._make_session = _local_session

def temp_sleep(seconds=0.1):
  pass  # no rate-limit delay needed for local inference

def ChatGPT_single_request(prompt):
  completion = _llm_call(lambda: openai.ChatCompletion.create(
    model=local_model,
    messages=[{"role": "user", "content": prompt}],
  ))
  return completion["choices"][0]["message"]["content"]


# ============================================================================
# #####################[SECTION 1: CHATGPT-3 STRUCTURE] ######################
# ============================================================================

def GPT4_request(prompt):
  try:
    completion = _llm_call(lambda: openai.ChatCompletion.create(
      model=local_model,
      messages=[{"role": "user", "content": prompt}],
    ))
    return completion["choices"][0]["message"]["content"]
  except Exception as e:
    print(f"ChatGPT ERROR: {e}")
    return "ChatGPT ERROR"


def ChatGPT_request(prompt):
  try:
    completion = _llm_call(lambda: openai.ChatCompletion.create(
      model=local_model,
      messages=[{"role": "user", "content": prompt}],
    ))
    return completion["choices"][0]["message"]["content"]
  except Exception as e:
    print(f"ChatGPT ERROR: {e}")
    return "ChatGPT ERROR"


def GPT4_safe_generate_response(prompt, 
                                   example_output,
                                   special_instruction,
                                   repeat=3,
                                   fail_safe_response="error",
                                   func_validate=None,
                                   func_clean_up=None,
                                   verbose=False): 
  prompt = 'GPT-3 Prompt:\n"""\n' + prompt + '\n"""\n'
  prompt += f"Output the response to the prompt above in json. {special_instruction}\n"
  prompt += "Example output json:\n"
  prompt += '{"output": "' + str(example_output) + '"}'

  if verbose: 
    print ("CHAT GPT PROMPT")
    print (prompt)

  for i in range(repeat): 

    try: 
      curr_gpt_response = GPT4_request(prompt).strip()
      end_index = curr_gpt_response.rfind('}') + 1
      curr_gpt_response = curr_gpt_response[:end_index]
      curr_gpt_response = json.loads(curr_gpt_response)["output"]
      
      if func_validate(curr_gpt_response, prompt=prompt):
        return func_clean_up(curr_gpt_response, prompt=prompt)

      if verbose:
        print ("---- repeat count: \n", i, curr_gpt_response)
        print (curr_gpt_response)
        print ("~~~~")

    except Exception:
      pass

  print ("GPT4 FAIL SAFE TRIGGERED")
  return fail_safe_response


def ChatGPT_safe_generate_response(prompt,
                                   example_output,
                                   special_instruction,
                                   repeat=3,
                                   fail_safe_response="error",
                                   func_validate=None,
                                   func_clean_up=None,
                                   verbose=False): 
  # prompt = 'GPT-3 Prompt:\n"""\n' + prompt + '\n"""\n'
  prompt = '"""\n' + prompt + '\n"""\n'
  prompt += f"Output the response to the prompt above in json. {special_instruction}\n"
  prompt += "Example output json:\n"
  prompt += '{"output": "' + str(example_output) + '"}'

  if verbose: 
    print ("CHAT GPT PROMPT")
    print (prompt)

  for i in range(repeat): 

    try: 
      curr_gpt_response = ChatGPT_request(prompt).strip()
      end_index = curr_gpt_response.rfind('}') + 1
      curr_gpt_response = curr_gpt_response[:end_index]
      curr_gpt_response = json.loads(curr_gpt_response)["output"]

      # print ("---ashdfaf")
      # print (curr_gpt_response)
      # print ("000asdfhia")
      
      if func_validate(curr_gpt_response, prompt=prompt):
        return func_clean_up(curr_gpt_response, prompt=prompt)

      if verbose:
        print ("---- repeat count: \n", i, curr_gpt_response)
        print (curr_gpt_response)
        print ("~~~~")

    except Exception:
      pass

  # All retries failed. Return the caller's fail_safe rather than False so
  # callers that don't guard against False never crash on `result[0]`.
  print ("CHATGPT FAIL SAFE TRIGGERED")
  return fail_safe_response


def ChatGPT_safe_generate_response_OLD(prompt,
                                   repeat=3,
                                   fail_safe_response="error",
                                   func_validate=None,
                                   func_clean_up=None,
                                   verbose=False): 
  if verbose: 
    print ("CHAT GPT PROMPT")
    print (prompt)

  for i in range(repeat): 
    try: 
      curr_gpt_response = ChatGPT_request(prompt).strip()
      if func_validate(curr_gpt_response, prompt=prompt): 
        return func_clean_up(curr_gpt_response, prompt=prompt)
      if verbose: 
        print (f"---- repeat count: {i}")
        print (curr_gpt_response)
        print ("~~~~")

    except Exception:
      pass
  print ("FAIL SAFE TRIGGERED") 
  return fail_safe_response


# ============================================================================
# ###################[SECTION 2: ORIGINAL GPT-3 STRUCTURE] ###################
# ============================================================================

def GPT_request(prompt, gpt_parameter):
  # Local models only expose the chat endpoint, not the legacy completions
  # endpoint, so we bridge by wrapping the prompt as a user message.
  try:
    completion = _llm_call(lambda: openai.ChatCompletion.create(
      model=local_model,
      messages=[{"role": "user", "content": prompt}],
      temperature=gpt_parameter.get("temperature", 0.7),
      max_tokens=gpt_parameter.get("max_tokens", 512),
      top_p=gpt_parameter.get("top_p", 1),
      frequency_penalty=gpt_parameter.get("frequency_penalty", 0),
      presence_penalty=gpt_parameter.get("presence_penalty", 0),
      stop=gpt_parameter.get("stop") or None,
    ))
    return completion["choices"][0]["message"]["content"]
  except Exception as e:
    print(f"TOKEN LIMIT EXCEEDED: {e}")
    return "TOKEN LIMIT EXCEEDED"


def generate_prompt(curr_input, prompt_lib_file): 
  """
  Takes in the current input (e.g. comment that you want to classifiy) and 
  the path to a prompt file. The prompt file contains the raw str prompt that
  will be used, which contains the following substr: !<INPUT>! -- this 
  function replaces this substr with the actual curr_input to produce the 
  final promopt that will be sent to the GPT3 server. 
  ARGS:
    curr_input: the input we want to feed in (IF THERE ARE MORE THAN ONE
                INPUT, THIS CAN BE A LIST.)
    prompt_lib_file: the path to the promopt file. 
  RETURNS: 
    a str prompt that will be sent to OpenAI's GPT server.  
  """
  if type(curr_input) == type("string"): 
    curr_input = [curr_input]
  curr_input = [str(i) for i in curr_input]

  f = open(prompt_lib_file, "r")
  prompt = f.read()
  f.close()
  for count, i in enumerate(curr_input):   
    prompt = prompt.replace(f"!<INPUT {count}>!", i)
  if "<commentblockmarker>###</commentblockmarker>" in prompt: 
    prompt = prompt.split("<commentblockmarker>###</commentblockmarker>")[1]
  return prompt.strip()


def safe_generate_response(prompt, 
                           gpt_parameter,
                           repeat=5,
                           fail_safe_response="error",
                           func_validate=None,
                           func_clean_up=None,
                           verbose=False): 
  if verbose: 
    print (prompt)

  for i in range(repeat): 
    curr_gpt_response = GPT_request(prompt, gpt_parameter)
    if func_validate(curr_gpt_response, prompt=prompt): 
      return func_clean_up(curr_gpt_response, prompt=prompt)
    if verbose: 
      print ("---- repeat count: ", i, curr_gpt_response)
      print (curr_gpt_response)
      print ("~~~~")
  return fail_safe_response


def get_embedding(text, model="all-MiniLM-L6-v2"):
  # sentence-transformers runs entirely locally — no API call needed.
  # all-MiniLM-L6-v2 (~80 MB) downloads once on first use.
  from sentence_transformers import SentenceTransformer
  text = text.replace("\n", " ") or "this is blank"
  _model = getattr(get_embedding, "_model", None)
  if _model is None or getattr(_model, "_name", None) != model:
    get_embedding._model = SentenceTransformer(model)
    get_embedding._model._name = model
  return get_embedding._model.encode(text).tolist()


if __name__ == '__main__':
  gpt_parameter = {"engine": "text-davinci-003", "max_tokens": 50, 
                   "temperature": 0, "top_p": 1, "stream": False,
                   "frequency_penalty": 0, "presence_penalty": 0, 
                   "stop": ['"']}
  curr_input = ["driving to a friend's house"]
  prompt_lib_file = "prompt_template/test_prompt_July5.txt"
  prompt = generate_prompt(curr_input, prompt_lib_file)

  def __func_validate(gpt_response): 
    if len(gpt_response.strip()) <= 1:
      return False
    if len(gpt_response.strip().split(" ")) > 1: 
      return False
    return True
  def __func_clean_up(gpt_response):
    cleaned_response = gpt_response.strip()
    return cleaned_response

  output = safe_generate_response(prompt, 
                                 gpt_parameter,
                                 5,
                                 "rest",
                                 __func_validate,
                                 __func_clean_up,
                                 True)

  print (output)




















