#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Listens to arriving emails and batch downloads attachments
import pickle
import base64
import collections
import os.path
import ast
import json
import piexif
import datetime
from subprocess import call
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import updateDbItems

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://mail.google.com/']
BASE_PATH = os.path.dirname(os.path.realpath(__file__)) + '/'


def main():
    alreadyRead = []
    filenames = []
    if os.path.exists(BASE_PATH + 'alreadyRead.json'):
        with open(BASE_PATH + 'alreadyRead.json', 'r') as json_file:
            alreadyRead = json.load(json_file)
            if type(alreadyRead) is not list:
                try:
                    alreadyRead = ast.literal_eval(alreadyRead)
                except:
                    print("Type translation failed")
    if os.path.exists(BASE_PATH + 'filenames.json'):
        with open(BASE_PATH + 'filenames.json', 'r') as json_file:
            filenames = json.load(json_file)
            if type(filenames) is not list:
                try:
                    filenames = ast.literal_eval(filenames)
                except:
                    print("Type translation failed")
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(BASE_PATH + 'token.pickle'):
        with open(BASE_PATH + 'token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                BASE_PATH + 'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(BASE_PATH + 'token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)

    # Call the Gmail API
    results = service.users().messages().list(
        userId='me', labelIds=['SENT']).execute()
    messages = results.get('messages', [])

    while 'nextPageToken' in results:
        page_token = results['nextPageToken']
        results = service.users().messages().list(userId='me', labelIds=[
            'SENT'], pageToken=page_token).execute()
        try:
            messages.extend(results['messages'])
        except:
            break
    list_of_read_ids = alreadyRead
    list_of_old_ids = list_of_read_ids[:]
    list_of_new_ids = []

    if not messages:
        print('No messages found.')
    else:
        for msg in messages:
            if msg['id'] in list_of_read_ids:
                list_of_new_ids.append(msg['id'])
                continue
            list_of_read_ids.append(msg['id'])
            list_of_new_ids.append(msg['id'])
            try:
                message = service.users().messages().get(
                    userId='me', id=msg['id']).execute()
                parts = [message['payload']]
                times = message['internalDate']
                timeas = times[:10]
                string_epoch = times

                try:
                    timestamp = datetime.datetime.fromtimestamp(int(timeas))
                except:
                    print("Timestamp creation failed")

                while parts:
                    part = parts.pop()
                    if part.get('parts'):
                        parts.extend(part['parts'])
                    if part.get('filename'):
                        if 'data' in part['body']:
                            file_data = base64.urlsafe_b64decode(
                                part['body']['data'].encode('UTF-8'))
                        elif 'attachmentId' in part['body']:
                            attachment = service.users().messages().attachments().get(
                                userId='me', messageId=message['id'], id=part['body']['attachmentId']
                            ).execute()
                            file_data = base64.urlsafe_b64decode(
                                attachment['data'].encode('UTF-8'))
                        else:
                            file_data = None
                        if file_data:
                            if part['mimeType'] == 'image/jpeg' or str(part['filename']).endswith(".jpg") or str(part['filename']).endswith(".JPG"):
                                fullFilename = ''.join(
                                    [message['id'], '_', string_epoch, '_', part['filename']])
                                path = ''.join(
                                    [BASE_PATH + 'images/', fullFilename])
                                if fullFilename not in filenames:
                                    filenames.append(fullFilename)
                                with open(path, 'wb') as f:
                                    f.write(file_data)
                                setExif(timestamp, path)
            except:
                print('Could not get payload from message')

    with open(BASE_PATH + 'filenames.json', 'w') as output:
        json.dump(filenames, output)
    if collections.Counter(list_of_old_ids) != collections.Counter(list_of_new_ids):
        list_of_read_ids = list_of_new_ids
        call([BASE_PATH + 'sync.sh'])
        updateDbItems.main()
    with open(BASE_PATH + 'alreadyRead.json', 'w') as output:
        json.dump(list_of_read_ids, output)


def setExif(timestamp, filename):
    try:
        formatted_timestamp = timestamp.strftime("%Y:%m:%d %H:%M:%S")
        exif_ifd = {piexif.ExifIFD.DateTimeOriginal: formatted_timestamp}
        exif_dict = {"Exif": exif_ifd}
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, filename)
    except:
        print("Exif insert failed")
    return


if __name__ == '__main__':
    main()
