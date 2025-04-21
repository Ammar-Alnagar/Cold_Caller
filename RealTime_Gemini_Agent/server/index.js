const express = require('express');
const nodemailer = require('nodemailer');
const bodyParser = require('body-parser');
const cors = require('cors');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(bodyParser.json());
app.use(cors());

// Configure Nodemailer transporter
const transporter = nodemailer.createTransport({
  host: 'smtp.gmail.com',
  port: 587,
  secure: false, // true for 465, false for other ports
  auth: {
    user: process.env.EMAIL_USER, // Your email address
    pass: process.env.EMAIL_PASS, // Your email password or app-specific password
  },
});

// Email sending endpoint
app.post('/api/sendEmail', async (req, res) => {
  const { to, subject, body, from } = req.body;

  const mailOptions = {
    from: from || process.env.EMAIL_USER,
    to,
    subject,
    text: body,
    html: body.includes('<html') ? body : `<p>${body}</p>`,
  };

  try {
    const info = await transporter.sendMail(mailOptions);
    console.log('Email sent: ' + info.response);
    res.status(200).json({ message: 'Email sent successfully', info });
  } catch (error) {
    console.error('Error sending email:', error);
    res.status(500).json({ error: 'Failed to send email', details: error.message });
  }
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).send('Email server is up and running');
});

app.listen(PORT, () => {
  console.log(`Email server running on port ${PORT}`);
}); 