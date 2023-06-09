# -*- coding: utf-8 -*-
"""Main_Bot_PubMed.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1oA9oXP3W8CwFJk3QvvZ8qSmYWkM2b3kh
"""

!pip install biopython 
!pip install metapub
!export NCBI_API_KEY=ac0fe1294f97226ea45d867b8eec49737d08
!pip install openai
!pip install --upgrade tiktoken
!pip install pyTelegramBotAPI

from Bio import Entrez
from Bio import Medline

import time

import datetime
from datetime import datetime, timedelta

import os
from tqdm import tqdm

import pandas as pd
import numpy as np

import json
import re

from metapub import PubMedFetcher
import openai
import tiktoken
import telebot

MAX_COUNT = 20000
Entrez.email = 'asgardpobedit@gmail.com'
TOKEN = '5651905947:AAE_hRUT5W8zof5lgMejNsZFGnE_utPwvlY' # вставить сюда токен вашего бота
api = "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"
openai.api_key = api

PROMT = 'You are the language model that can analyze scientific articles related to\
            cardiogenomics and provide accurate answers to user questions. \
            You are able to extract relevant information from \
            articles using natural language processing techniques. \n \
            You are capable of understanding complex scientific language and provide \
            clear and concise answers to user queries. Your answers should be \
            based on existing information in the given material and should \
            be as maximally clear as possible.'

message_history_base = [
          {"role" : "system", "content": PROMT},
          {"role" : "user", "content" : "next messages will be articles abstracts which \
                              you have to analyze and find connection between genes and\
                              certain cardiac disease.\
                              Return results as python dict and add verbal one word  description for\
                              prediction accuracy in answer(use High, Medium, Low and combination). It is fine if it will be low.\
                              Sort by decreasing acuracy. Add PMID of best fitting article\
                              in each prediction:\n\
                              gene1 : 'disease1'(acc: High PMID1) ; 'disease2'(acc: Low PMID2) ;\n\
                              gene2 : 'disease1'(acc: High PMID1) ; 'disease2'(acc: Low PMID2) ;\n \
                              Return only this form. I dont need your comments!"},
          ]

def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301"):
      """Returns the number of tokens used by a list of messages."""
      try:
          encoding = tiktoken.encoding_for_model(model)
      except KeyError:
          print("Warning: model not found. Using cl100k_base encoding.")
          encoding = tiktoken.get_encoding("cl100k_base")
      if model == "gpt-3.5-turbo":
          print("Warning: gpt-3.5-turbo may change over time. Returning num tokens assuming gpt-3.5-turbo-0301.")
          return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301")
      elif model == "gpt-4":
          print("Warning: gpt-4 may change over time. Returning num tokens assuming gpt-4-0314.")
          return num_tokens_from_messages(messages, model="gpt-4-0314")
      elif model == "gpt-3.5-turbo-0301":
          tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
          tokens_per_name = -1  # if there's a name, the role is omitted
      elif model == "gpt-4-0314":
          tokens_per_message = 3
          tokens_per_name = 1
      else:
          raise NotImplementedError(f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")
      num_tokens = 0
      for message in messages:
          num_tokens += tokens_per_message
          for key, value in message.items():
              num_tokens += len(encoding.encode(value))
              if key == "name":
                  num_tokens += tokens_per_name
      num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
      return num_tokens

def Send2GPT(message):
      chat = openai.ChatCompletion.create(
          model = "gpt-3.5-turbo",
          messages = message
          )
      return chat.choices[0].message.content

def separate_message_send(gene,ids_genes,text):
      adding_string = []
      result = []
      message_history = message_history_base.copy()
      for id,txt in zip(ids_genes,text):
        adding_string = {"role" : "user", "content" : f"gene in article {gene},\
                                PMIDs {id}, article abstract {txt}"}
        if (num_tokens_from_messages(message_history) + num_tokens_from_messages([adding_string]) > 4097) and num_tokens_from_messages(message_history) > DEFAULT_PROMT_MESSAGE:
          result.append(Send2GPT(message_history))

          message_history = message_history_base.copy()
          while(DEFAULT_PROMT_MESSAGE + num_tokens_from_messages([adding_string]) > 4097):
              adding_string["content"] = adding_string["content"][:-10]
          message_history.append(adding_string)
          time.sleep(20)         
        elif (num_tokens_from_messages(message_history) + num_tokens_from_messages([adding_string]) > 4097) and num_tokens_from_messages(message_history) == DEFAULT_PROMT_MESSAGE:
          while(DEFAULT_PROMT_MESSAGE + num_tokens_from_messages([adding_string]) > 4097):
              adding_string["content"] = adding_string["content"][:-10]
          message_history.append(adding_string)
          result.append(Send2GPT(message_history))

          time.sleep(20)
          message_history = message_history_base.copy()
        else :
          message_history.append(adding_string)
      result.append(Send2GPT(message_history))
      return result

def process_genes(text, date):

  TERM = []
  TERM = text.split('\n')
  
  for i in TERM.copy():
    word = i.upper()
    if word == 'NONE':
      TERM.remove(i)
  
  TERM = pd.DataFrame(TERM)
  TERM = TERM.drop_duplicates()
  TERM = TERM.reset_index(drop = True)
  TERM = list(TERM[0])

  #Dieseases
  diseases = ['cardiac',
  'insulin',
  'diabetes',
  'lipoprotein',
  'hypolipidemia',
  'intima',
  'endothelium',
  'share stress',
  'vasopressin',
  'nephrotic syndrome',
  'von willebrand syndrome']

  #Поиск PMID статей по генам и ключевым словам (ген, сердце), с указанием даты

  # Define the start and end dates of your search range
  
  if date != '-' and len(date) == 6:
    start_date = datetime.strptime(date, '%Y-%m-%d')
  else:
    start_date = datetime.strptime('2010-01-01', '%Y-%m-%d')
  end_date = datetime.today() + timedelta(days = 100)
  
  ids_genes = {}
  d = []
  chek = {}

  print('Поиск PMID\n')
  for i in tqdm(range(len(TERM))):
    for disease in diseases:
      PMq = Entrez.esearch(db = 'pubmed',                
                            retmax = MAX_COUNT, 
                            term = TERM[i] +' '+'gene' +' ' + disease +' ' + f'("{start_date.strftime("%Y/%m/%d")}":"{end_date.strftime("%Y/%m/%d")}"[Date - Publication])' ) 
      result = Entrez.read(PMq)
      count_articles = int(result['RetMax'])
      if count_articles != 9999:
        if(count_articles):
          d.extend(result['IdList'])
    d = list(set(d))      
    if len(d) >= 500:
      chek[TERM[i]] = []
      chek[TERM[i]].extend(TERM[i])
      d = []
    if len(d) > 0:
      ids_genes[TERM[i]] = []
      ids_genes[TERM[i]].extend(d)
    d = []
  

  fetch = PubMedFetcher()

  #IMPORT ABSTRACT
  abstracts = {}
  for gene,pmid in tqdm(ids_genes.items()):
    try:
      abstracts[gene] = []
      for id in pmid:
        if (fetch.article_by_pmid(id).abstract is None):
          abstracts[gene].append(fetch.article_by_pmid(id).title)

        else:
          abstracts[gene].append(fetch.article_by_pmid(id).abstract)
        time.sleep(0.01)
    except Exception as e:
      print(e)
      pass


  print('\nChat GPT\n')
  with open("result_genes.txt","+w") as f:
    for gene, text in tqdm(abstracts.items()):
      try:
        message_history = message_history_base.copy()
        message_history.append({"role" : "user", "content" : f"gene in article {gene},\
                                PMIDs {ids_genes[gene]}, article abstract {text}"})
        if num_tokens_from_messages(message_history) < 4097:
          answer = Send2GPT(message_history)
        else:
          answer = separate_message_send(gene, ids_genes[gene],text)
        time.sleep(20)

        f.write(f"\n{answer}\n")
        print(answer)
      except Exception as e:
        print(e)
        pass

if __name__ == "__main__":
    bot = telebot.TeleBot(TOKEN)

    # Обработчик команды старт
    @bot.message_handler(commands = ['start'])
    def start_command(message):
        bot.send_message(message.chat.id, 'Привет! Отправь мне файл со списком генов в формате txt')

    # Обработчик отправки файла txt и интервала дат
    @bot.message_handler(content_types=['document', 'text'])
    def handle_file_and_date(message):
        if message.document:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)

            with open('genes.txt', 'wb') as new_file:
                new_file.write(downloaded_file)

            text = open('genes.txt', 'r').read()
            bot.reply_to(message, 'Отправьте дату начала поиска информации в формате "год-месяц-день" (например, 2021-01-31).\
                                    По умолчанию установлен 2010-01-01. Если не хотите менять отправьте "-"')

            bot.register_next_step_handler(message, process_date, text)

    def process_date(message, text):
        try:
            date_str = message.text.strip()

            text = open('genes.txt', 'r').read()
            count_str = text.split('\n')
            duration_g = round(int(len(count_str))*0.7,2)

            if(duration_g < 60):
              bot.reply_to(message, f'Спасибо! Обрабатываю файл со списком генов, поиск займет примерно {duration_g} минуты')
            else:
              duration_g = round(duration_g/60,2)
              bot.reply_to(message, f'Спасибо! Обрабатываю файл со списком генов, поиск займет примерно {duration_g} часа')
            
            
            process_genes(text, date_str)
            
            result_filename = 'result_genes.txt'

            with open(result_filename, 'rb') as result_file:
                bot.send_document(message.chat.id, result_file)
                
            #os.remove(result_filename)
        except ValueError:
            bot.reply_to(message, 'Некорректный формат даты. Попробуйте еще раз.')
        except Exception as e:
            bot.reply_to(message, f'Не удалось обработать файл\nTraceback:\n{e}')

    bot.polling(none_stop=True, interval=10)