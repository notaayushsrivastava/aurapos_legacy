from dataclasses import dataclass
import sqlite3 as sql
from datetime import datetime
from flask import g

def get_db():
    return sql.connect("database.db", autocommit=True)
    



@dataclass
class Time:
  day = 24*60*60
  month = 30*day
  year = 365*day


@dataclass
class Service:
  id : int
  name : str
  price : int
  staff : Staff

  def to_dict(self):
    return {
      "id" : self.id,
      "name":self.name,
      "price":self.price,
      "staff":self.staff
    }
  
  @classmethod
  def from_dict(cls, dict:dict):
    return cls(
      id=dict["id"],
      name=dict["name"],
      price=dict["price"],
      staff=dict["staff"]
    )

@dataclass
class Staff:
  id : int
  name : str
  total_revenue : int
  created_on : int

@dataclass
class Bill:
  id : int
  services : list[Service]
  date : int

@dataclass
class Salon:
  id : int
  name : str
  phone : int
  salon_name : str
  email : str
  created_on : int
  plan : str
  expires_on : int

  @classmethod
  def from_row(cls, row:tuple):
    try:
      return cls(
        id = row[0],
        name = row[1],
        phone = row[2],
        salon_name = row[3],
        email = row[4],
        created_on = row[5],
        plan = row[6],
        expires_on = row[7]
      )
    except:
      return None

@dataclass
class Account:
  auth_id : int
  username : str
  password : str
  auth_level : str
  salon : Salon|None

  @classmethod
  def from_row(cls, row:tuple):
    try:
      conn = get_db()
      cur = conn.cursor()
      e = cur.execute("SELECT * FROM SALON WHERE id = ?", (row[0],)).fetchone()
      conn.close()
      return cls(
        auth_id = row[0], 
        username = row[1], 
        password = row[2], 
        auth_level = row[3],
        salon = Salon.from_row(e)
      )
    except: return None
  



class AuthorizationRepository:
  def __init__(self):
    conn = get_db()
    cur=conn.cursor()
    cur.executescript(
        """
          CREATE TABLE IF NOT EXISTS salon(
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            salon_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            created_on INTEGER NOT NULL,
            plan TEXT NOT NULL,
            expires_on INTEGER NOT NULL
          );

          CREATE TABLE IF NOT EXISTS accounts(
            auth_id INTEGER NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            auth_level TEXT DEFAULT 'admin',

            FOREIGN KEY (auth_id) REFERENCES salon(id)
          );

          CREATE TABLE IF NOT EXISTS pendingorders(
            id TEXT PRIMARY KEY,
            amount INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            plan TEXT NOT NULL,
            receipt TEXT NOT NULL,
            email TEXT NOT NULL,
            phone INTEGER NOT NULL,
            salon_id INTEGER DEFAULT 0
          );

          CREATE TABLE IF NOT EXISTS subscriptions(
            id TEXT PRIMARY KEY,
            amount INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            plan TEXT NOT NULL,
            receipt TEXT NOT NULL,
            email TEXT NOT NULL,
            phone INTEGER NOT NULL,
            salon_id INTEGER DEFAULT 0
          );
        """

    )
    conn.close()
    
  def create_account(self, auth_id ,username, password, auth_level='admin'):
    conn = get_db()
    cur=conn.cursor()
    cur.execute(
      """
        INSERT INTO accounts(
          auth_id, username, password, auth_level
        ) VALUES (?, ?, ?, ?)
      """, (auth_id, username, password, auth_level)
    )
    conn.close()
  
  def create_auth(self, name, salon_name,phone, email, password, plan, created_on=int(datetime.now().timestamp()), auth_level='admin'):
    conn = get_db()
    cur=conn.cursor()
    auth_id = cur.execute(
      """
        INSERT INTO salon(
          name, salon_name, phone, email, plan, created_on, expires_on
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
      """,
      (name, salon_name, phone, email, plan, created_on, created_on+Time.month if plan=='monthly' else created_on+Time.year,)
    ).lastrowid
    conn.close()

    self.create_account(auth_id, email, password, auth_level)
  
  def login(self, username, password):
    conn = get_db()
    cur=conn.cursor()
    e=cur.execute("SELECT * FROM accounts WHERE username = ? AND password = ?", (username,password,)).fetchone()
    conn.close()
    return Account.from_row(e)
  
  
    
  
  

