import sys
import argparse
import torch
from evaluate import Evaluator
from dataset import GraphDataset
from models import *
from torch_geometric.loader import DataLoader


parser = argparse.ArgumentParser()
parser.add_argument('--dataset', type=str, default='1')
parser.add_argument('--hidden_channels', type=int, default=64)
parser.add_argument('--lr', type=float, default=0.001)
parser.add_argument('--epochs', type=int, default=100)
parser.add_argument('--batch_size', type=int, default=128)
parser.add_argument('--model', type=str, default='GCN')
parser.add_argument('--layers', type=int, default=2)
parser.add_argument('--normalize', type=int, default=1)

args = parser.parse_args()

BATCH_SIZE = args.batch_size
NUM_EPOCHS = args.epochs

X_train = GraphDataset(f"./dataset/dataset_{args.dataset}/train")
X_val = GraphDataset(f"./dataset/dataset_{args.dataset}/valid")

train_loader = DataLoader(X_train, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(X_val, batch_size=len(X_val), shuffle=True)

# if torch.cuda.is_available():
#     device = torch.device('cuda')
# elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
#     device = torch.device('mps')
# else:
#     device = torch.device('cpu')

device = torch.device('cpu')

string_to_models = {
    "GCN" : GNN_TYPE.GCN,
    "GAT" : GNN_TYPE.GAT,
    "GIN" : GNN_TYPE.GIN,
    "SAGE" : GNN_TYPE.SAGE
}

model = BaselineRegressor(args.hidden_channels)
if args.model != "Baseline":
    model = GNN_common_regressor(args.hidden_channels, 1, 128, string_to_models[args.model], args.layers, (args.normalize == 1))
optimizer = torch.optim.Adam(model.parameters(),lr=args.lr, weight_decay=5e-4)
optimizer.zero_grad()
loss_fun = torch.nn.MSELoss()

for epoch in range(NUM_EPOCHS):
    model.train()
    model.to(device)
    total_loss = 0.0
    for i, batch in enumerate(train_loader):
        
        # Move batch to device
        batch.to(device)
       
        # Forward pass
        out = model(batch.x, batch.edge_index.to(torch.long), batch.edge_attr, batch.batch, batch.y.shape[0])
        
        # Calculate and print loss
        optimizer.zero_grad()
        loss = loss_fun(out.reshape(1, -1), batch.y.reshape(1, -1))

        # Backward pass and optimization
        loss.mean().backward(retain_graph=True)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        total_loss+=loss.item()


    average_loss = total_loss / len(train_loader)

     # Validation phase
    model.eval()
    with torch.no_grad():
        total_bce = 0.0
        
        for i, batch in enumerate(val_loader):
             # Move batch to device
            batch.to(device)
            if(batch.edge_index.shape[0] == 0):
                continue
            # Forward pass
            out = model(batch.x, batch.edge_index.to(torch.long), batch.edge_attr, batch.batch, batch.y.shape[0])
            loss = loss_fun(out.reshape(1, -1), batch.y.reshape(1, -1))
            loss = loss.mean()

            total_bce += loss.item()

        average_bce_val = total_bce / len(val_loader)

    # Print logs
    if epoch % 10 == 0:
        print(f"Epoch {epoch+1}/{NUM_EPOCHS}, Train Loss: {average_loss:.4f} , Val MSE: {average_bce_val:.4f}")
        sys.stdout.flush()
# Make sure to clear the computation graph after the loop
torch.cuda.empty_cache()

evaluator = Evaluator('dataset-1')
val_loader = DataLoader(X_val, batch_size= len(X_val), shuffle = False)

for i, batch in enumerate(val_loader):
    model.eval()
    # Move batch to device
    batch.to(device)
    # Forward pass
    y_pred = model(batch.x, batch.edge_index.to(torch.long), batch.edge_attr, batch.batch, batch.y.shape[0])
    y_true = batch.y
    y_true = y_true.unsqueeze(1)

    input_dict = {'y_true': y_true, 'y_pred': y_pred}
    result = evaluator.eval(input_dict)
    print(result)
    sys.stdout.flush()