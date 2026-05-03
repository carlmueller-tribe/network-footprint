import express from 'express';

const router = express.Router();

router.get('/users', (req, res) => {
  res.json([]);
});

router.post('/users', (req, res) => {
  res.status(201).json({ id: '1' });
});

router.delete('/users/:id', (req, res) => {
  res.status(204).send();
});

export default router;
