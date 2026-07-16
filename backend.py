from dataclasses import dataclass
import sqlite3 as sql
import razorpay

conn = sql.connect("database.db")
cur = conn.cursor()

rzp_client = razorpay.Client(
    auth=("rzp_test_SxU2RG4SoMaOcI", "nYTCHgr6NQy1b5X0VDEXcELO")
)



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


class AuthRepo:
  def __init__(self):
    cur.execute(
      """
        CREATE TABLE IF NOT EXISTS auth(
          id INTEGER PRIMARY KEY AUTOINCREMENT, 
          name TEXT NOT NULL,
          phone TEXT NOT NULL,
          email TEXT NOT NULL,
          created_on INTEGER NOT NULL,
          

        )
      """
    )