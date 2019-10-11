#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Listens to arriving emails and batch downloads attachments
from __future__ import print_function
import pickle
import base64
import os.path
import ast
import json
import piexif
import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from apiclient import errors

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def main():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    alreadyRead = []
    if os.path.exists('alreadyRead.json'):
        with open('alreadyRead.json', 'r') as json_file:
            alreadyRead = json.load(json_file)
            if type(alreadyRead) is not list:
                try:
                    alreadyRead = ast.literal_eval(alreadyRead)
                except:
                    print("Type translation failed")
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
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
        messages.extend(results['messages'])

    list_of_read_ids = alreadyRead

    if not messages:
        print('No messages found.')
    else:
        for msg in messages:
            if msg['id'] in list_of_read_ids:
                continue
            list_of_read_ids.append(msg['id'])
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
                                print(part['filename'])
                                path = ''.join(
                                    ['/home/pi/work_ssd/email1/images/', message['id'], '_', string_epoch, '_', part['filename']])
                                with open(path, 'wb') as f:
                                    f.write(file_data)
                                setExif(timestamp, path)
            except:
                print('Could not get payload from message')

    with open('alreadyRead.json', 'w') as output:
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
