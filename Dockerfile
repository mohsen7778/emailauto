schemaVersion: 1.2

endpoints:
  - name: cold-email-api
    displayName: Cold Email Bot API
    service:
      basePath: /
      port: 8000
    type: REST
    networkVisibilities:
      - Public

configurations:
  env:
    - name: TELEGRAM_BOT_TOKEN
      valueFrom:
        configForm:
          displayName: Telegram Bot Token
          type: secret
          required: true
    
    - name: ADMIN_CHAT_IDS
      valueFrom:
        configForm:
          displayName: Admin Telegram Chat IDs
          type: string
          required: true
    
    - name: MONGO_URI
      valueFrom:
        configForm:
          displayName: MongoDB Atlas URI
          type: secret
          required: true
    
    - name: BREVO_API_KEY
      valueFrom:
        configForm:
          displayName: Brevo API Key
          type: secret
          required: true
    
    - name: SENDER_EMAIL
      valueFrom:
        configForm:
          displayName: Sender Email
          type: string
          required: true
