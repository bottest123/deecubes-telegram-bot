import os
from telegram import MessageEntity
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

import config
from utils import restricted
from links import LinkProcessor
from files import FileProcessor


class Handlers:

  updater = None
  links_processor = None
  files_processor = None

  def __init__(self):
    self.updater = Updater(token=config.BOT_TOKEN)
    dispatcher = self.updater.dispatcher
    self.links_processor = LinkProcessor()
    self.files_processor = FileProcessor()

    dispatcher.add_handler(CommandHandler('start', self.start))
    dispatcher.add_handler(CommandHandler('paste', self.paste))
    dispatcher.add_handler(CommandHandler('pasten', self.paste_named))
    dispatcher.add_handler(CommandHandler('pastei', self.paste_image))
    dispatcher.add_handler(
      MessageHandler(
        Filters.audio | Filters.video | Filters.photo | Filters.document | Filters.voice,
        self.process_files
      )
    )
    dispatcher.add_handler(
      MessageHandler(
        Filters.text & (Filters.entity(MessageEntity.URL) | Filters.entity(MessageEntity.TEXT_LINK)),
        self.process_links
      )
    )

    self.updater.start_polling()
    self.updater.idle()

  def start(self, bot, update):
    update.message.reply_text(text="Hello! Send me a link or file but tread with caution. I only tend to my master.")

  @restricted
  def paste(self, bot, update):
    self.process_paste(update, '/paste')

  @restricted
  def paste_named(self, bot, update):
    self.process_paste(update, '/pasten')

  @restricted
  def paste_image(self, bot, update):
    self.process_paste(update, '/pastei')

  def process_paste(self, update, paste_command):
    context = {
      'chat_id': update.message.chat_id,
      'message_id': update.message.message_id,
      'text': update.message.text,
      'paste_command': paste_command,
    }
    update.message.reply_text('Processing', quote=True)
    self.updater.job_queue.run_once(self.process_paste_queue, 0, context=context)

  def process_paste_queue(self, bot, job):
    command = job.context['paste_command']
    make_img = False
    file_name = None
    if command == '/pastei':
      make_img = True
    if command == '/pasten':
      data = job.context['text'].split(' ', 2)
      file_name = os.path.basename(data[1])
    else:
      data = job.context['text'].split(' ', 1)
    content = data[-1]

    url = self.files_processor.process_paste(content, file_name, make_img)
    if url:
      text = 'Paste uploaded to ' + url
      shorturl = self.links_processor.process_link(url)
      if shorturl:
        text += '\nShorturl: ' + shorturl
    else:
      text = 'Could not upload paste'

    bot.send_message(
      chat_id=job.context['chat_id'],
      reply_to_message_id=job.context['message_id'],
      text=text
    )

  @restricted
  def process_links(self, bot, update):
    context = {
      'chat_id': update.message.chat_id,
      'message_id': update.message.message_id,
      'text': update.message.text,
      'entities': update.message.entities
    }
    update.message.reply_text('Processing', quote=True)
    self.updater.job_queue.run_once(self.process_links_queue, 0, context=context)

  def process_links_queue(self, bot, job):
    for entry in job.context['entities']:
      if entry.url:
        url = entry.url
      else:
        url = job.context['text'][entry.offset:entry.offset + entry.length]
      shorturl = self.links_processor.process_link(url)
      if shorturl:
        text = 'Shorturl ' + shorturl + ' created for ' + url
      else:
        text = 'Could not create shorturl for ' + url

      bot.send_message(
        chat_id=job.context['chat_id'],
        reply_to_message_id=job.context['message_id'],
        text=text
      )

  @restricted
  def process_files(self, bot, update):
    context = {
      'message': update.message,
    }
    update.message.reply_text('Processing', quote=True)
    self.updater.job_queue.run_once(self.process_files_queue, 0, context=context)

  def process_files_queue(self, bot, job):
    message = job.context['message']
    content = message.effective_attachment

    if isinstance(content, list):
      for c in content:
        self.process_single_file(bot, message, c)
    else:
      self.process_single_file(bot, message, content)

  def process_single_file(self, bot, message, content):
    try:
      file_obj = bot.get_file(content.file_id)
      try:
        # Original file name is only given for documents
        file_name = content.file_name
      except AttributeError:
        file_name = os.path.basename(file_obj.file_path)
      url = self.files_processor.process_file(file_obj, file_name)
      if url:
        text = 'File uploaded to ' + url
        shorturl = self.links_processor.process_link(url)
        if shorturl:
          text += '\nShorturl: ' + shorturl
      else:
        text = 'Could not upload file'
    except AttributeError:
      text = 'Unsupported file type'

    bot.send_message(
      chat_id=message.chat_id,
      reply_to_message_id=message.message_id,
      text=text
    )
