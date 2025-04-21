# Email Server

This is a simple Express server for sending emails using Nodemailer. It provides an API endpoint that the frontend React application can call to send emails.

## Setup

1. **Install Dependencies**: Run `npm install` in this directory to install the required packages.

2. **Configure Email Credentials**:

   - Create a `.env` file in this directory with your email credentials:
     ```
     EMAIL_USER=your-email@gmail.com
     EMAIL_PASS=your-app-specific-password
     ```
   - For Gmail, you may need to use an App Password if 2FA is enabled. Generate one in your Google Account settings.

3. **Run the Server**:
   - Start the server with `npm start` for production or `npm run dev` for development with auto-restart on file changes.
   - The server runs on port 3001 by default. You can change this by setting the `PORT` environment variable.

## API Endpoints

- **POST /api/sendEmail**: Send an email. The request body should include:

  ```json
  {
    "to": "recipient@example.com",
    "subject": "Email Subject",
    "body": "Email content here",
    "from": "optional-sender@example.com" // Optional, defaults to EMAIL_USER
  }
  ```

- **GET /health**: Check if the server is running.

## Security Notes

- Never commit your `.env` file with sensitive credentials to version control.
- For production, consider using a more secure email service or SMTP relay.
- Ensure CORS is configured appropriately for your frontend domain in production.
