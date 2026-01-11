import z from 'zod'

export const signupSchema = z
  .object({
    username: z.string().min(1).max(64),
    email: z.email().min(1),
    password: z.string().min(8).max(40),
    confirmPassword: z.string().min(8).max(40),
    agreeToTerms: z.boolean(),
  })
  .refine((v) => v.password === v.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })
  .refine((v) => v.agreeToTerms === true, {
    message: 'You must agree to the terms',
    path: ['agreeToTerms'],
  })

