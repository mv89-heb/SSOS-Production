import { apiClient } from "./api-client";
import { User, UserRole } from "@/types";

export interface CreateUserInput {
  email: string;
  full_name: string;
  password: string;
  role: UserRole;
}

export interface UpdateUserInput {
  email?: string;
  full_name?: string;
  password?: string;
  role?: UserRole;
  active?: boolean;
}

export const userService = {
  async list(): Promise<User[]> {
    const { data } = await apiClient.get<{ success: boolean; users: User[] }>("/api/users");
    return data.users;
  },

  async create(input: CreateUserInput): Promise<User> {
    const { data } = await apiClient.post<{ success: boolean; user: User }>("/api/users", input);
    return data.user;
  },

  async update(id: number, input: UpdateUserInput): Promise<User> {
    const { data } = await apiClient.put<{ success: boolean; user: User }>(`/api/users/${id}`, input);
    return data.user;
  },
};
